"""STIX 2.1 Threat Intelligence Export for Enterprise SIEM integration."""
import json
import uuid
from datetime import datetime, timezone

def generate_stix_bundle(findings, case_id: str) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds") + "Z"
    
    objects = []
    
    # Create the Identity (Aaina System)
    identity_id = f"identity--{uuid.uuid4()}"
    objects.append({
        "type": "identity",
        "spec_version": "2.1",
        "id": identity_id,
        "created": now,
        "modified": now,
        "name": "Aaina Threat Monitor",
        "identity_class": "system"
    })
    
    for f in findings:
        if f.bucket not in ("Urgent", "Review"):
            continue
            
        indicator_id = f"indicator--{uuid.uuid4()}"
        
        objects.append({
            "type": "indicator",
            "spec_version": "2.1",
            "id": indicator_id,
            "created": now,
            "modified": now,
            "name": f"Misused Photo on {f.domain}",
            "description": f"Potential photo misuse or impersonation detected. Risk: {f.score}",
            "indicator_types": ["malicious-activity", "impersonation"],
            "pattern": f"[url:value = '{f.page_url}']",
            "pattern_type": "stix",
            "valid_from": now
        })
        
        # Add a Sighting
        objects.append({
            "type": "sighting",
            "spec_version": "2.1",
            "id": f"sighting--{uuid.uuid4()}",
            "created": now,
            "modified": now,
            "first_seen": now,
            "last_seen": now,
            "count": 1,
            "sighting_of_ref": indicator_id,
            "where_sighted_refs": [identity_id]
        })

    bundle = {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid4()}",
        "objects": objects
    }
    
    return json.dumps(bundle, indent=2)
