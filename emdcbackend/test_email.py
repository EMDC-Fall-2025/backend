"""
Quick test script to send an email via Resend
"""
import os
import sys
import django

# Setup Django to load environment variables
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emdcbackend.settings')
django.setup()

from emdcbackend.auth.utils import send_email_via_resend

# Test sending email to verified address
try:
    print("Sending test email to emdc.contest@gmail.com...")
    result = send_email_via_resend(
        to_email="emdc.contest@gmail.com",
        subject="Test Email from EMDC",
        html_content="<h2>Hello!</h2><p>This is a test email from your EMDC application.</p><p>If you received this, your Resend integration is working correctly! ✅</p>",
        text_content="Hello!\n\nThis is a test email from your EMDC application.\n\nIf you received this, your Resend integration is working correctly!"
    )
    print(f"✅ Email sent successfully!")
    print(f"Email ID: {result.get('id')}")
    print(f"\nCheck your inbox at emdc.contest@gmail.com")
except Exception as e:
    print(f"❌ Error sending email: {e}")
    import traceback
    traceback.print_exc()

