"""Aaina API: Enterprise REST Backend.
Run with: uvicorn api:app --reload
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os

from aaina.pipeline import build_runtime, prepare_inputs, run_sweep
from aaina.config import Settings
from aaina.fusion import IgnoreRules

app = FastAPI(
    title="Aaina Enterprise API",
    description="Headless API for the Aaina image misuse monitor.",
    version="2.0.0"
)

class SweepRequest(BaseModel):
    urls: List[str]
    ignore_domains: Optional[str] = ""

class FindingResponse(BaseModel):
    url: str
    domain: str
    risk_bucket: str
    score: int
    engines: List[str]
    reasons: List[str]

@app.get("/")
def health_check():
    return {"status": "online", "service": "Aaina Enterprise API"}

@app.post("/v1/sweep", response_model=dict)
def run_api_sweep(req: SweepRequest):
    if not req.urls:
        raise HTTPException(status_code=400, detail="At least one image URL must be provided.")
    if len(req.urls) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 URLs allowed per API sweep to prevent server exhaustion.")
    
    settings = Settings.load()
    if not settings.api_key and not settings.demo:
        raise HTTPException(status_code=500, detail="SERPAPI_API_KEY not configured on server.")

    client, fetch = build_runtime(settings)
    
    try:
        # We only accept public URLs via the API for security reasons
        refs, originals, shas = prepare_inputs(client, req.urls, [])
        result = run_sweep(client, refs, originals, settings, IgnoreRules.from_text(req.ignore_domains), fetch)
        
        # Serialize findings
        findings_out = []
        for f in result.findings:
            findings_out.append(FindingResponse(
                url=f.page_url,
                domain=f.domain,
                risk_bucket=f.bucket,
                score=f.score,
                engines=f.engines,
                reasons=[r[0] for r in f.reasons]
            ))
            
        return {
            "status": "success",
            "metrics": {
                "urgent": sum(1 for f in findings_out if f.risk_bucket == "Urgent"),
                "review": sum(1 for f in findings_out if f.risk_bucket == "Review"),
                "low": sum(1 for f in findings_out if f.risk_bucket == "Low"),
                "total_matches": len(findings_out)
            },
            "findings": findings_out,
            "reports": [{"engine": r.engine, "ok": r.ok, "hits": r.hits} for r in result.reports]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
