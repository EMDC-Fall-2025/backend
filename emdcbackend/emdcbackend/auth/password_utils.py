from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from .utils import send_email_via_resend

def build_set_password_url(user) -> str:
    """
    Create a URL that the frontend can use to set/reset the password.
    Example local:
      http://127.0.0.1:5173/set-password/?uid=<uid>&token=<token>&email=<user.username>
    """
    import os
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    # Check environment variable first, then settings, then default
    frontend_base = os.environ.get("FRONTEND_BASE_URL") or getattr(settings, "FRONTEND_BASE_URL", "http://127.0.0.1:5173")
    frontend_base = frontend_base.rstrip("/")
    return f"{frontend_base}/set-password/?uid={uid}&token={token}&email={user.username}"

def send_set_password_email(user, *, subject=None):
    """
    Sends a set/reset password email to the user's email (username).
    Uses Resend SDK to send emails with professional HTML formatting.
    """
    subject = subject or "Set your EMDC account password"
    link = build_set_password_url(user)
    
    # Plain text version
    text_content = f"""Hello,

An account has been created for {user.username}.

Please set your password using the link below:

{link}

If you did not expect this, you can ignore this email.

---
EMDC Contest Management System
"""
    
    # Professional HTML version
    html_content = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #2563eb;">Set Your Password</h2>
    
    <p>Hello,</p>
    
    <p>An account has been created for <strong>{user.username}</strong>.</p>
    
    <p>Please click the button below to set your password:</p>
    
    <div style="margin: 30px 0;">
        <a href="{link}" 
           style="background-color: #2563eb; 
                  color: white; 
                  padding: 12px 24px; 
                  text-decoration: none; 
                  border-radius: 5px;
                  display: inline-block;
                  font-weight: bold;">
            Set Password
        </a>
    </div>
    
    <p>Or copy and paste this link into your browser:</p>
    <p style="background-color: #f3f4f6; padding: 10px; border-radius: 5px; word-break: break-all; font-family: monospace; font-size: 12px;">
        {link}
    </p>
    
    <p style="color: #6b7280; margin-top: 30px;">
        If you did not expect this email, you can safely ignore it.
    </p>
    
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
    
    <p style="color: #9ca3af; font-size: 12px;">
        EMDC Contest Management System<br>
        This is an automated email, please do not reply.
    </p>
</div>
"""
    
    send_email_via_resend(
        to_email=user.username,
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )
