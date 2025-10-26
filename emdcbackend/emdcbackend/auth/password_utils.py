from django.conf import settings
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
