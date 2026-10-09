"""Automated Legal Dispatcher: Send DMCA/IT Rules notices via Email."""
import smtplib
from email.message import EmailMessage
import os

def send_legal_notice(to_email: str, subject: str, body: str, case_file_bytes: bytes = None):
    # For hackathon/demo purposes, we simulate the send if credentials aren't set
    sender_email = os.environ.get("AAINA_SMTP_EMAIL")
    sender_pass = os.environ.get("AAINA_SMTP_PASS")
    
    if not sender_email or not sender_pass:
        print(f"--- SIMULATED EMAIL DISPATCH ---")
        print(f"TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(f"BODY:\n{body[:200]}...")
        print("--------------------------------")
        return True, "Simulated email sent successfully (Add SMTP credentials to .env for real delivery)"
        
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email
        msg.set_content(body)
        
        if case_file_bytes:
            msg.add_attachment(case_file_bytes, maintype='application', subtype='pdf', filename='Aaina_Evidence.pdf')
            
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_pass)
            smtp.send_message(msg)
            
        return True, f"Legally binding notice sent to {to_email}"
    except Exception as e:
        return False, str(e)
