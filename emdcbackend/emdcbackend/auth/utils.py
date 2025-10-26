from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator

def build_set_password_url(user) -> str:
    """
    Build a URL the frontend can use to set/reset the password.
    Expecting settings.FRONTEND_BASE_URL (we set this in settings.py).
    Example link:
      http://127.0.0.1:5173/set-password/?uid=...&token=...&email=...
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
    return f"{frontend_base}/set-password/?uid={uid}&token={token}&email={user.username}"

def send_set_password_email(user) -> None:
    """
    Send a set/reset password email. In dev we use console backend,
    so it prints to the Django console.
    """
    link = build_set_password_url(user)
    subject = "Set your EMDC account password"
    message = (
        f"Hello,\n\n"
        f"An account has been created for {user.username}.\n"
        f"Please set your password using the link below:\n\n"
        f"{link}\n\n"
        f"If you did not expect this, you can ignore this email."
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@emdc.local")
    send_mail(subject, message, from_email, [user.username], fail_silently=False)
