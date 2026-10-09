"""Takedown kit: ready-to-send notices and the right route for each kind of site.

Aaina cannot delete anything on other websites. It prepares the paperwork.
Legal references are pointers, not legal advice. Verify current text before sending."""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from .urls import registrable

ISSUES = {
    "impersonation": ("Impersonation / fake profile",
                      "This page uses my photograph to impersonate me or present me falsely. "
                      "I did not authorise this."),
    "ncii": ("Non-consensual intimate or morphed imagery",
             "This page shows imagery of me that is sexually explicit, or that has been altered or "
             "morphed to appear so. I did not consent to its creation or publication."),
    "copyright": ("Unauthorised use of my photograph",
                  "I took, or otherwise own the copyright in, the original photograph shown on this "
                  "page. It is used without my permission."),
    "privacy": ("Privacy violation",
                "My photograph is published without my consent and is causing me harm."),
}

ROUTES = {
    "social": ["Use the platform's in-app Report option on the post or profile "
               "(choose impersonation, nudity/sexual content, or harassment as applicable).",
               "Send the notice below to the platform's Grievance Officer. Large platforms must "
               "publish this contact in their Help or Legal pages."],
    "image_host": ["Use the host's Report / Abuse / DMCA page (usually linked in the footer).",
                   "Send the notice below. If the host does not respond, contact its hosting provider's abuse address."],
    "adult": ["Do not engage with the site's operators. Use the site's removal form if one exists, "
              "otherwise the hosting provider's abuse address (see abuse_contact in this kit).",
              "Ask Google to remove the page from Search using its removal request for involuntary "
              "explicit or fake imagery (search the Google Help Centre for that title).",
              "If you hold the intimate image yourself, StopNCII.org creates a hash on your own "
              "device so participating platforms can block it. The image is never uploaded."],
    "dating": ["Use the platform's Report profile option (fake profile / stolen photos).",
               "Send the notice below to the platform's Grievance Officer."],
    "unknown": ["Look for a Contact, Report, DMCA or Abuse page on the site.",
                "If there is none, send the notice to the hosting provider's abuse address "
                "(see abuse_contact in this kit)."],
}

COMMON = """\
FOR EVERY CASE
- Report on the National Cyber Crime Reporting Portal: https://cybercrime.gov.in
- Helpline: 1930
- Keep this case file (PDF + JSON). Do not delete messages, links or screenshots.
- If you are in danger or being threatened, contact your local police or a trusted person first.
- Verify every link and legal reference on its official page before relying on it.

⚡ Parallel action recommended: StopNCII.org
StopNCII creates a fingerprint of your image ON YOUR DEVICE (never uploads it)
and automatically notifies major platforms to remove matching content.
Website: https://stopncii.org/
This is free and works in India.
"""


@dataclass
class Applicant:
    name: str
    email: str
    phone: str = ""


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%d %B %Y")


def get_country_code(host: str) -> str:
    try:
        r = requests.get(f"http://ip-api.com/json/{host}?fields=countryCode", timeout=3)
        return r.json().get("countryCode", "UNKNOWN")
    except Exception:
        return "UNKNOWN"

def platform_notice(f, a: Applicant, issue: str, case_id: str, country_code: str = "UNKNOWN") -> str:
    label, why = ISSUES[issue]
    
    if country_code == "IN":
        law_ref = "Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021, Rule 3(2)(b)"
        action = "Failure to act may be reported to the Ministry of Electronics and Information Technology (MeitY) and to the cybercrime portal at cybercrime.gov.in."
        timeframe = "within 24 hours"
    elif country_code in ("GB", "FR", "DE", "IT", "ES", "NL", "IE", "SE", "PL", "EU"):
        law_ref = "General Data Protection Regulation (GDPR) Article 17 (Right to Erasure) and the EU Digital Services Act (DSA) Article 16"
        action = "Failure to act may result in a formal complaint to the national Data Protection Authority (DPA)."
        timeframe = "without undue delay"
    elif country_code == "US":
        law_ref = "Digital Millennium Copyright Act (DMCA) and relevant state privacy laws (e.g. CCPA)"
        action = "Failure to act expeditiously may result in loss of safe harbor protections and civil liability."
        timeframe = "expeditiously"
    else:
        law_ref = "international privacy and intermediary liability standards"
        action = "Failure to act may result in formal legal action and reporting to your hosting provider."
        timeframe = "immediately"

    return f"""\
Subject: Urgent removal request under {law_ref.split('(')[0].strip()} - {label} - {f.page_url}

To the Grievance Officer / Trust & Safety Team,

I am {a.name} ({a.email}). I am writing to request the immediate removal of content 
at the URL below, which contains my photograph posted without my consent:

    {f.page_url}

What is wrong
{why}

What I am asking you to do
1. Remove or disable access to the content at the URL above {timeframe}.
2. Confirm removal in writing and give me a complaint reference number.
3. Preserve the related records for law enforcement.

Under the {law_ref}, you are required to act on complaints of this kind {timeframe}.

{action}

My case reference: {case_id}

Regards,
{a.name}
{a.email}
{('Phone: ' + a.phone) if a.phone else ''}
Date: {_today()}
"""


def dmca_notice(f, a: Applicant, case_id: str) -> str:
    return f"""\
DMCA / COPYRIGHT NOTICE (use ONLY if you took the photo or own its copyright)

To the Designated Agent,

1. Copyrighted work: an original photograph that I own. Available on request.
2. Infringing material: {f.page_url}
3. Contact: {a.name}, {a.email}
4. I have a good-faith belief that this use is not authorised by me, my agent, or the law.
5. The information in this notice is accurate, and I am the owner (or authorised to act for the
   owner) of the exclusive right that is allegedly infringed.

Signed: {a.name}    Date: {_today()}    Case reference: {case_id}
"""


def cybercrime_draft(findings, a: Applicant, case_id: str, manifest: str) -> str:
    lines = [f"  {i}. {f.page_url}\n     first found {f.first_seen}; engines: {', '.join(sorted(f.engines))}; "
             f"risk {f.bucket} ({f.score})" for i, f in enumerate(findings, 1)]
    return f"""\
COMPLAINT DRAFT FOR cybercrime.gov.in   (edit before submitting)

Complainant: {a.name}, {a.email}
Case reference: {case_id}

Summary
My photographs have been found published, copied, or altered on the pages listed below, without
my consent. I do not know who is responsible. I request that a complaint be registered and the
content be taken down.

Pages
{chr(10).join(lines)}

Evidence
A case file (PDF and JSON) is attached. Its integrity fingerprint (SHA-256) is:
  {manifest}
Search results were gathered on the dates shown by running reverse-image searches on my own
original photographs. They are possible matches and have been reviewed by me.

Relief requested
Registration of the complaint, removal of the content, and preservation of related records.
(The police will determine the applicable sections, for example under the Information
Technology Act, 2000, and the Bharatiya Nyaya Sanhita.)

{a.name}    {_today()}
"""


INDIA_GRIEVANCE_OFFICERS = {
    "instagram.com":  "india_grievance@support.instagram.com",
    "facebook.com":   "india_grievance@support.facebook.com",
    "twitter.com":    "grievance-officer@twitter.com",
    "x.com":          "grievance-officer@twitter.com",
    "sharechat.com":  "grievance@sharechat.com",
    "telegram.org":   "abuse@telegram.org",
    "reddit.com":     "legal@reddit.com",
}

def get_grievance_contact(domain: str) -> str | None:
    for platform, contact in INDIA_GRIEVANCE_OFFICERS.items():
        if platform in domain:
            return contact
    return None

# ---------------------------------------------------------------- hosting abuse contact (best effort)
def _vcard_email(vcard):
    try:
        for item in vcard[1]:
            if item[0] == "email":
                return item[3]
    except (IndexError, TypeError):
        pass
    return None


def find_abuse_email(node):
    """Walk an RDAP JSON document and return the first entity with the 'abuse' role's email."""
    if isinstance(node, dict):
        if "abuse" in (node.get("roles") or []):
            email = _vcard_email(node.get("vcardArray"))
            if email:
                return email
        for v in node.values():
            found = find_abuse_email(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = find_abuse_email(v)
            if found:
                return found
    return None


def rdap_abuse_contact(host: str, timeout: int = 8):
    try:
        r = requests.get(f"https://rdap.org/domain/{registrable(host)}", timeout=timeout)
        return find_abuse_email(r.json()) if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


# ---------------------------------------------------------------- the kit
def build_kit(selected, a: Applicant, issue: str, case_id: str, manifest: str, lookup_abuse=None) -> dict:
    kit = {"00_READ_ME_FIRST.txt": COMMON,
           "01_cybercrime_complaint_draft.txt": cybercrime_draft(selected, a, case_id, manifest)}
           
    geo_cache = {} # Fix: Prevent N+1 rate limiting on ip-api.com
    
    for i, f in enumerate(selected, 1):
        steps = "\n".join(f"  - {s}" for s in ROUTES.get(f.domain_class, ROUTES["unknown"]))
        
        abuse = get_grievance_contact(f.domain)
        if not abuse:
            abuse = (lookup_abuse(f.domain) if lookup_abuse else None) or "not found. Search the host with a WHOIS/RDAP tool"
            
        if f.domain not in geo_cache:
            geo_cache[f.domain] = get_country_code(f.domain)
        cc = geo_cache[f.domain]
        
        body = (f"ROUTE FOR {f.domain}  ({f.domain_class})\n{steps}\n\nabuse_contact: {abuse}\n\n"
                f"{'=' * 70}\n\n{platform_notice(f, a, issue, case_id, cc)}")
        if issue == "copyright":
            body += f"\n{'=' * 70}\n\n{dmca_notice(f, a, case_id)}"
        kit[f"10_notice_{i:02d}_{f.domain.replace('.', '_')}.txt"] = body
    return kit


def kit_zip(kit: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in kit.items():
            z.writestr(name, text)
    return buf.getvalue()
