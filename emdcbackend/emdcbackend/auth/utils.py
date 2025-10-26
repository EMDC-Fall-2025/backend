from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator

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

def send_set_password_email(user, *, subject=None):
    """
    Sends a set/reset password email to the user's email (username).
    Uses console email backend in dev, so the link will print in the Django console.
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
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@emdc.local")
    send_mail(subject, body, from_email, [user.username], fail_silently=False)
