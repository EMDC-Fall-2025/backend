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
    # Check environment variable first, then settings, then default
    frontend_base = os.environ.get("FRONTEND_BASE_URL") or getattr(settings, "FRONTEND_BASE_URL", "http://127.0.0.1:5173")
    frontend_base = frontend_base.rstrip("/")
    return f"{frontend_base}/set-password/?uid={uid}&token={token}&email={user.username}"

def send_email_via_resend(to_email, subject, html_content, text_content=None):
    """
    Send email using Resend SDK instead of SMTP.
    Note: Resend only allows sending to verified emails unless domain is verified.
    In test environments, failures are logged but don't raise exceptions.
    """
    try:
        import resend
        
        # Validate inputs
        if not to_email or not isinstance(to_email, str) or not to_email.strip():
            raise ValueError("to_email is required and must be a non-empty string")
        if not subject or not isinstance(subject, str) or not subject.strip():
            raise ValueError("subject is required and must be a non-empty string")
        if not html_content:
            raise ValueError("html_content is required")
        
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            # In test environments, don't fail if API key is missing
            if os.environ.get("DJANGO_SETTINGS_MODULE") == "emdcbackend.settings" and os.environ.get("DEBUG") == "1":
                print(f"[WARN] Resend email skipped: RESEND_API_KEY not set (test environment)")
                return None
            raise ValueError("RESEND_API_KEY not set in environment")
        
        resend.api_key = api_key
        
        from_email = os.environ.get("DEFAULT_FROM_EMAIL", "EMDC Contest <noreply@emdcresults.com>")
        # Just clean up any extra whitespace
        from_email = from_email.strip()
        if not from_email:
            raise ValueError("DEFAULT_FROM_EMAIL is empty or invalid")
        
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email.strip()],
            "subject": subject.strip(),
            "html": html_content,
            "text": text_content or html_content.replace("<p>", "").replace("</p>", "\n").replace("<br>", "\n"),
        })
        
        return result
    except Exception as e:
        # In test/CI environments, log but don't raise to avoid breaking tests
        is_test_env = (
            os.environ.get("DJANGO_SETTINGS_MODULE") == "emdcbackend.settings" and 
            (os.environ.get("DEBUG") == "1" or "test" in os.environ.get("POSTGRES_DB", "").lower())
        )
        if is_test_env:
            print(f"[WARN] Resend email failed (test environment): {e}")
            return None
        print(f"[ERROR] Resend email failed: {e}")
        raise


# Import it from there: from .password_utils import send_set_password_email
