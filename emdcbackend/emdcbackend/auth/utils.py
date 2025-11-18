from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
import os

def build_set_password_url(user) -> str:
    """
    Create a URL that the frontend can use to set/reset the password.
    Example local:
      http://127.0.0.1:5173/set-password/?uid=<uid>&token=<token>&email=<user.username>
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
    return f"{frontend_base}/set-password/?uid={uid}&token={token}&email={user.username}"

def send_email_via_resend(to_email, subject, html_content, text_content=None):
    """
    Send email using Resend SDK instead of SMTP.
    Note: Resend only allows sending to verified emails unless domain is verified.
    """
    try:
        import resend
        
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            raise ValueError("RESEND_API_KEY not set in environment")
        
        resend.api_key = api_key
        
        from_email = os.environ.get("DEFAULT_FROM_EMAIL", "onboarding@resend.dev")
        # Extract email from "Name <email>" format if needed
        if "<" in from_email and ">" in from_email:
            from_email = from_email.split("<")[1].split(">")[0].strip()
        
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": text_content or html_content.replace("<p>", "").replace("</p>", "\n").replace("<br>", "\n"),
        })
        
        return result
    except Exception as e:
        print(f"[ERROR] Resend email failed: {e}")
        raise

def send_set_password_email(user, *, subject=None):
    """
    Sends a set/reset password email to the user's email (username).
    Uses Resend SDK to send emails.
    """
    subject = subject or "Set your EMDC account password"
    link = build_set_password_url(user)
    body = (
        "Hello,\n\n"
        f"An account has been created for {user.username}.\n"
        "Please set your password using the link below:\n\n"
        f"{link}\n\n"
        "If you did not expect this, you can ignore this email."
    )
    
    html_body = body.replace("\n", "<br>")
    send_email_via_resend(
        to_email=user.username,
        subject=subject,
        html_content=f"<p>{html_body}</p>",
        text_content=body
    )
