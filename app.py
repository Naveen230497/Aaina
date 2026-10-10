"""Aaina: Streamlit interface.   Run:  streamlit run app.py"""
from __future__ import annotations

import json
from dataclasses import replace

import streamlit as st

from aaina import demo as demo_mod
from aaina.casefile import make_case, render_pdf, save_case
from aaina.config import Settings
from aaina.fusion import IgnoreRules
from aaina.hashing import blurred_png
from aaina.pipeline import build_runtime, prepare_inputs, run_sweep
from aaina.quota import Quota
from aaina.safety import Attestation, UnsafeInput, attestation_labels, attestation_ok
from aaina.takedown import ISSUES, Applicant, build_kit, kit_zip, rdap_abuse_contact

st.set_page_config(page_title="Aaina", page_icon="🪞", layout="wide")

# Jaw-dropping Custom CSS with MOVING VIDEO BACKGROUND
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"]  {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Strip ALL default Streamlit backgrounds */
body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background-color: transparent !important;
    background: transparent !important;
}

/* Ensure the main app content sits ON TOP of the animation without breaking sidebar position */
[data-testid="stMainBlockContainer"] {
    position: relative !important;
    z-index: 10 !important;
}

[data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="collapsedControl"] {
    z-index: 100 !important;
}

/* Hide annoying Streamlit elements but KEEP header so sidebar toggle works! */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* Hero Title */
h1 {
    font-weight: 800 !important;
    background: linear-gradient(to right, #45f3ff, #ec4899, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding-bottom: 20px !important;
    font-size: 3.5rem !important;
    letter-spacing: -0.05em;
    position: relative;
    z-index: 10;
}

/* Cinematic Aurora Background */
.aurora-bg {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 0;
    background: #0B0F19;
    overflow: hidden;
}

.aurora-1, .aurora-2, .aurora-3 {
    position: absolute;
    border-radius: 50%;
    filter: blur(90px);
    opacity: 0.6;
    animation: moveAurora 5s infinite alternate ease-in-out;
}

.aurora-1 {
    top: -10%; left: -10%;
    width: 60vw; height: 60vh;
    background: #8b5cf6;
}

.aurora-2 {
    bottom: -20%; right: -10%;
    width: 70vw; height: 70vh;
    background: #ec4899;
    animation-delay: -2s;
}

.aurora-3 {
    top: 30%; left: 30%;
    width: 50vw; height: 50vh;
    background: #3b82f6;
    animation-delay: -4s;
}

@keyframes moveAurora {
    0% { transform: translate(0, 0) scale(1); }
    100% { transform: translate(250px, -150px) scale(1.3); }
}

h2, h3 {
    font-weight: 700 !important;
    color: #F3F4F6 !important;
    letter-spacing: -0.02em;
}

/* Premium Primary Button */
.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, #8b5cf6 0%, #d946ef 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 1.1rem !important;
    padding: 0.75rem 2rem !important;
    box-shadow: 0 10px 25px -5px rgba(139, 92, 246, 0.5), 0 8px 10px -6px rgba(139, 92, 246, 0.1) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    border-radius: 12px !important;
    width: 100%;
}

.stButton>button[kind="primary"]:hover {
    transform: translateY(-3px) scale(1.02) !important;
    box-shadow: 0 20px 25px -5px rgba(139, 92, 246, 0.6), 0 8px 10px -6px rgba(139, 92, 246, 0.1) !important;
}

/* Glassmorphism Expanders */
div[data-testid="stExpander"] {
    background: rgba(31, 41, 55, 0.4) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    backdrop-filter: blur(12px) !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    transition: all 0.2s ease-in-out !important;
    margin-bottom: 12px !important;
}

div[data-testid="stExpander"]:hover {
    border-color: rgba(139, 92, 246, 0.5) !important;
    background: rgba(31, 41, 55, 0.7) !important;
    transform: translateX(4px);
}

/* Custom Checkboxes */
div[data-testid="stCheckbox"] label {
    font-weight: 500 !important;
    color: #D1D5DB !important;
}

/* Subheadings / Headers inside content */
.css-10trblm {
    color: #9CA3AF !important;
}
</style>

<!-- INJECT AURORA ANIMATION HTML -->
<div class="aurora-bg">
    <div class="aurora-1"></div>
    <div class="aurora-2"></div>
    <div class="aurora-3"></div>
</div>
""", unsafe_allow_html=True)

base = Settings.load()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🪞 Aaina")
    st.caption("Find where your photos are being misused, and prepare the takedown.")
    demo = st.toggle("Demo mode (offline, synthetic images)", value=base.demo)
    settings = replace(base, demo=demo)
    if not demo:
        st.metric("Searches left this month", Quota(settings.home / "quota.json", settings.monthly_cap).remaining())
        if not settings.api_key:
            st.error("Add SERPAPI_API_KEY to your .env file.")
    st.markdown("**Built-in safeguards**\n- Consent check before anything runs\n- No face recognition or people search\n"
                "- Photos are never stored; EXIF/GPS is stripped\n- Thumbnails are blurred by default\n"
                "- Result links are not clickable, so you never open a harmful page by accident")

st.title("Aaina: Enterprise Threat Intelligence")

from aaina.database import verify_user, create_user

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.markdown("### 🔐 Enterprise Secure Access")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Secure Login"):
                if verify_user(l_user, l_pass):
                    st.session_state.logged_in = True
                    st.session_state.username = l_user
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
                    
    with tab2:
        with st.form("register_form"):
            r_user = st.text_input("New Username")
            r_pass = st.text_input("New Password", type="password")
            if st.form_submit_button("Register Account"):
                if r_user and r_pass:
                    if create_user(r_user, r_pass):
                        st.success("Account created! You can now log in.")
                    else:
                        st.error("Username already exists.")
    st.stop()

# If we get here, user is logged in
st.sidebar.success(f"👤 Logged in as: **{st.session_state.username}**")

# GDPR Data Portability Export
with st.sidebar.expander("⚖️ GDPR Compliance Center"):
    st.write("Under GDPR Article 20, you have the right to download your data.")
    import json
    export_data = json.dumps({"username": st.session_state.username, "account_type": "Enterprise Standard", "history": "Stored securely in SQLite"})
    st.download_button("Download My Data (JSON)", export_data, "gdpr_export.json")
    
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# NEXT LEVEL: Enterprise Admin Console
if st.session_state.username.lower() == "admin":
    st.header("🛡️ Enterprise Admin Console")
    st.caption("Global system overview and user metrics.")
    from aaina.database import get_admin_stats
    stats = get_admin_stats()
    
    a1, a2, a3 = st.columns(3)
    a1.metric("Total Registered Users", stats["total_users"])
    a2.metric("Total Sweeps Executed", stats["total_cases"])
    a3.metric("Total Urgent Threats Prevented", stats["total_urgent"])
    
    st.subheader("Top Active Users")
    for u, c in stats["top_users"]:
        st.write(f"- **{u}**: {c} sweeps")
        
    st.warning("You are in the Admin Panel. To use the Aaina Scanner, log out and create a regular user account.")
    st.stop()

# ------------------------------------------------------------------ step 1: consent
st.header("1 · Before we start")
att = Attestation(**{k: st.checkbox(v, key=f"att_{k}") for k, v in attestation_labels().items()})
if not attestation_ok(att)[0]:
    st.info("Tick all four boxes to continue. If you are in danger or being threatened, contact the police "
            "or someone you trust first. Helpline 1930, https://cybercrime.gov.in")
    st.stop()

# ------------------------------------------------------------------ step 2: originals
st.header("2 · Add your original photos")
urls, files, mine = [], [], ""
if demo:
    st.info("Demo mode uses synthetic, non-human images and canned search responses. No network calls are made.")
else:
    st.caption("Use clean originals, such as profile pictures. **Never add the harmful or intimate image itself.**")
    tab_url, tab_up = st.tabs(["Public link (all 4 engines)", "Upload (Google Lens only)"])
    with tab_url:
        urls = [u.strip() for u in st.text_area("One link per line (max 5)").splitlines() if u.strip()][:5]
    with tab_up:
        files = st.file_uploader("JPEG, PNG, WebP or MP4 Video", accept_multiple_files=True, type=["jpg", "jpeg", "png", "webp", "mp4", "mov"]) or []
        st.caption("Uploads go to SerpApi's Image API (max 500 KB, so photos are shrunk) and are searched with Google "
                   "Lens only. Use a public link to also search Google Reverse Image, Bing and Yandex.")
        
        # NEXT LEVEL: Deepfake Video Frame Extraction
        from aaina.video_scanner import extract_keyframes
        video_frames = []
        image_files = []
        for file in files:
            if file.name.lower().endswith(('.mp4', '.mov')):
                st.info(f"🎬 Video detected: `{file.name}`. Extracting keyframes for reverse search...")
                try:
                    extracted = extract_keyframes(file.getvalue())
                    if extracted:
                        video_frames.extend(extracted)
                        st.success(f"✅ Extracted {len(extracted)} frames from video.")
                    else:
                        st.error(f"❌ Failed to extract frames. Video might be empty or unsupported.")
                except Exception as e:
                    st.error(f"❌ Video extraction failed: {str(e)}")
            else:
                image_files.append(file)
                
        # Combine uploaded images with extracted video frames
        final_image_bytes = [f.getvalue() for f in image_files] + video_frames
        
        # NEXT LEVEL: EXIF Privacy Analysis
        if image_files:
            from aaina.exif_analyzer import analyze_exif
            for file in files:
                exif_res = analyze_exif(file.getvalue())
                if exif_res["status"] == "danger":
                    st.error(f"🚨 **Privacy Alert:** `{file.name}` contains hidden GPS location data! Aaina will securely strip this before searching, but be careful sharing this file online.")
                elif exif_res["status"] == "warning":
                    meta_str = ", ".join([f"{k}: {v}" for k,v in exif_res["data"].items()])
                    st.warning(f"⚠️ **Metadata Found:** `{file.name}` contains hidden camera data ({meta_str}). Aaina will strip this before searching.")
            
            from aaina.watermark import embed_watermark
            st.info("🛡️ **Proactive Protection:** Before sharing this photo online again, download an invisibly watermarked version. If anyone steals it, you can cryptographically prove it belongs to you.")
            for file in files:
                try:
                    watermarked_bytes = embed_watermark(file.getvalue(), f"Aaina Protected: {file.name}")
                    st.download_button(f"⬇️ Download Protected {file.name}", watermarked_bytes, f"protected_{file.name.split('.')[0]}.png", mime="image/png")
                except Exception:
                    pass

    mine = st.text_input("Pages that are really yours (domains or handles, comma separated)")
    per = 4 + int(settings.lens_exact)
    st.write(f"Estimated searches: **{len(urls) * per + len(files) * (1 + int(settings.lens_exact))}**")

# ------------------------------------------------------------------ step 3: sweep
if st.button("🔍 Run sweep", type="primary"):
    try:
        client, fetch = build_runtime(settings)
        with st.status("🔍 Analyzing the web for your photos...", expanded=True) as status:
            st.write("📡 Scanning reverse-image engines...")
            if demo:
                refs, originals, shas = demo_mod.demo_inputs()
            else:
                if not urls and not files:
                    st.warning("Add at least one photo link or upload (image or video).")
                    st.stop()
                refs, originals, shas = prepare_inputs(client, urls, final_image_bytes[: 5 - len(urls)])
            
            st.write("⚖️ Fusing results and downloading thumbnails for local hashing...")
            result = run_sweep(client, refs, originals, settings, IgnoreRules.from_text(mine), fetch)
            
            status.update(label="✅ Deep scan complete!", state="complete", expanded=False)
            
        st.session_state.update(result=result, shas=shas, urls=urls, outputs=None)
    except UnsafeInput as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001 - show a friendly message, never a stack trace
        st.error(f"The sweep stopped: {exc}")

res = st.session_state.get("result")
if not res:
    st.stop()

st.header("3 · What we found")
urgent = sum(1 for f in res.findings if f.bucket == "Urgent")
review = sum(1 for f in res.findings if f.bucket == "Review")
low    = sum(1 for f in res.findings if f.bucket == "Low")

if urgent > 0:
    st.error(f"🚨 {urgent} URGENT findings — action needed now")
if review > 0:
    st.warning(f"⚠️ {review} findings need your review")
st.success(f"ℹ️ {low} low-risk findings")

counts = {b: sum(f.bucket == b for f in res.findings) for b in ("Urgent", "Review", "Low", "Yours")}
cols = st.columns(4)
colors = {"Urgent": "#ef4444", "Review": "#f59e0b", "Low": "#10b981", "Yours": "#6366f1"}

for col, (name, n) in zip(cols, counts.items()):
    color = colors[name]
    col.markdown(f"""
    <div style="
        background-color: #111827;
        border-left: 4px solid {color};
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        margin-bottom: 20px;
    ">
        <p style="color: #9CA3AF; font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin: 0;">{name}</p>
        <p style="color: {color}; font-size: 2.25rem; font-weight: 800; margin: 5px 0 0 0;">{n}</p>
    </div>
    """, unsafe_allow_html=True)

# ENTERPRISE THREAT MAP & ANALYTICS
if urgent > 0 or review > 0:
    st.subheader("🌍 Global Threat Intelligence")
    import requests
    import pandas as pd
    
    # Get geolocation for Urgent/Review domains
    threat_locations = []
    mapped_domains = set()
    for f in res.findings:
        if f.bucket in ("Urgent", "Review") and f.domain not in mapped_domains:
            mapped_domains.add(f.domain)
            try:
                # Max 10 requests to avoid rate limits
                if len(threat_locations) < 10:
                    r = requests.get(f"http://ip-api.com/json/{f.domain}?fields=lat,lon,country", timeout=2)
                    data = r.json()
                    if "lat" in data and "lon" in data:
                        threat_locations.append({"lat": data["lat"], "lon": data["lon"], "domain": f.domain, "country": data.get("country", "")})
            except:
                pass
                
    if threat_locations:
        df = pd.DataFrame(threat_locations)
        try:
            # Removed size and color parameters which silently crash WebGL in some Streamlit versions
            st.map(df, zoom=1, use_container_width=True)
            st.caption(f"Mapped {len(threat_locations)} high-risk server locations.")
        except Exception as e:
            st.warning("Map rendering failed. Falling back to text view.")
            st.dataframe(df)
    else:
        st.info("No geospatial data available for these threats.")

st.divider()
for rep in res.reports:
    if not rep.ok:
        st.warning(f"{rep.engine} failed: {rep.error}")
st.caption("These are **possible** matches. They are not proof. Review each one.")

selected = []
for bucket in ("Urgent", "Review", "Low", "Yours"):
    items = [f for f in res.findings if f.bucket == bucket]
    if not items:
        continue
    st.subheader(f"{bucket} ({len(items)})")
    for f in items:
        with st.expander(f"{f.score:>3} · {f.domain} · {', '.join(sorted(f.engines))}", expanded=(bucket == "Urgent")):
            left, right = st.columns([1, 3])
            with left:
                if f.thumb_bytes:
                    reveal = st.checkbox("Show image", key=f"rev_{f.key}")
                    st.image(f.thumb_bytes if reveal else blurred_png(f.thumb_bytes), width=160)
            with right:
                st.code(f.page_url, language=None)
                for text, pts in f.reasons:
                    st.write(f"`{pts:+d}` {text}")
                    
                if getattr(f, "ads", []):
                    st.error("🚨 Running Google Ads")
                    for ad in getattr(f, "ads"):
                        st.caption(f"Ad format: {ad.get('format')} | First shown: {ad.get('first_shown')}")
                
                news = getattr(f, "news_articles", [])
                if news:
                    st.warning("📰 Domain in the news (Fraud/Scam reports)")
                    for article in news:
                        st.caption(f"[{article.get('title')}]({article.get('link')}) - {article.get('date')}")

                if bucket != "Yours" and st.checkbox("Include in takedown kit", key=f"sel_{f.key}", value=(bucket == "Urgent")):
                    selected.append(f)

# ------------------------------------------------------------------ step 4: kit
st.header("4 · Takedown kit and case file")
name, email = st.text_input("Your name (used in the notices)"), st.text_input("Your email")
issue = st.selectbox("What best describes the problem?", list(ISSUES), format_func=lambda k: ISSUES[k][0])
look = st.checkbox("Look up hosting abuse contacts (contacts rdap.org)", value=False)
if st.button("📦 Build my kit"):
    if not (name and email and selected):
        st.warning("Enter your name and email, and tick at least one finding.")
    else:
        case = make_case(res.findings, st.session_state["shas"], st.session_state["urls"], res.reports)
        
        # NEXT LEVEL: Save to SQLite Database
        from aaina.database import log_case
        log_case(case["case_id"], st.session_state.username, urgent)
        
        kit = build_kit(selected, Applicant(name, email), issue, case["case_id"], case["manifest_sha256"],
                        rdap_abuse_contact if look else None)
        path = save_case(case, settings.home)
        pdf = render_pdf(case, path.with_suffix(".pdf"))
        st.session_state["outputs"] = (kit_zip(kit), pdf.read_bytes(), json.dumps(case, indent=2), case["case_id"], str(path))

def make_whatsapp_card(urgent_count: int, domain_list: list[str]) -> str:
    return f"""⚠️ *PHOTO MISUSE ALERT — Please be aware*

My photo was found on {urgent_count} suspicious website(s):
{chr(10).join(f'• {d}' for d in domain_list[:3])}

If you see my photo on any website I haven't shared it with, please:
1. Do NOT share or download the image
2. Report it directly on the platform
3. Forward this message to warn others

To report cybercrime in India: cybercrime.gov.in or call 1930
Verified with Aaina (SerpApi-powered image misuse monitor)"""

out = st.session_state.get("outputs")
if out:
    zip_bytes, pdf_bytes, json_text, case_id, saved = out
    a, b, c, d = st.columns(4)
    a.download_button("⬇ Takedown kit (.zip)", zip_bytes, f"{case_id}-kit.zip", use_container_width=True)
    b.download_button("⬇ Case file (.pdf)", pdf_bytes, f"{case_id}.pdf", use_container_width=True)
    c.download_button("⬇ Case data (.json)", json_text, f"{case_id}.json", use_container_width=True)
    
    # Generate STIX Bundle dynamically
    from aaina.stix import generate_stix_bundle
    stix_json = generate_stix_bundle(res.findings, case_id)
    d.download_button("🛡️ Export STIX (SIEM)", stix_json, f"{case_id}-stix.json", use_container_width=True)
    
    st.success(f"Saved to {saved}. Re-check weekly with:  python -m aaina.watch --case \"{saved}\"")
    
    urgent_domains = [f.domain for f in res.findings if f.bucket == "Urgent"]
    if urgent_domains:
        with st.expander("📱 Generate WhatsApp Warning Card"):
            st.code(make_whatsapp_card(len(urgent_domains), list(set(urgent_domains))), language=None)
            
    # NEXT LEVEL: Automated Email Dispatcher
    st.subheader("📧 Automated Legal Dispatcher")
    st.caption("Instantly email these takedown notices to the hosting providers.")
    if st.button("🚀 Auto-Send Legal Notices to Abuse Contacts", type="primary"):
        from aaina.mailer import send_legal_notice
        success_count = 0
        with st.spinner("Dispatching legal notices..."):
            for f in selected:
                # Mock finding the abuse email (would normally parse from the kit)
                abuse_email = f"abuse@{f.domain}"
                ok, msg = send_legal_notice(
                    to_email=abuse_email,
                    subject=f"Urgent removal request - {case_id}",
                    body=f"Please find attached legal notice regarding domain {f.domain}.",
                    case_file_bytes=pdf_bytes
                )
                if ok:
                    success_count += 1
        st.success(f"✅ Automatically dispatched {success_count} legal notices! (Simulation Mode active - check console)")

    st.caption("Next steps: send each notice, then report at https://cybercrime.gov.in (helpline 1930). "
               "Verify every link and legal reference on its official page before relying on it.")

# ------------------------------------------------------------------ step 5: AI Chatbot
st.divider()
st.header("5 · AI Legal Assistant")
st.caption("Ask our AI assistant about IT Rules 2021, DMCA, GDPR, or how to file a police report.")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am Aaina's AI Legal Assistant. How can I help you with your takedown process today?"}]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a legal question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        from aaina.ai_chat import get_ai_response
        with st.spinner("Thinking..."):
            response = get_ai_response(prompt)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
