# backend/emdcbackend/emdcbackend/auth/password_views.py
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .password_utils import build_set_password_url


# 1) Admin/Organizer re-sends a set-password email (auth required)
@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def request_set_password(request):
    """
    Body: { "username": "<email>" }
    Sends a set-password link to the user's email. Typically used for first-time users.
    """
    username = request.data.get("username")
    if not username:
        return Response({"detail": "username (email) is required."}, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, username=username)

    url = build_set_password_url(user)
    subject = "Set your password"
    message = (
        f"Hello,\n\n"
        f"Please click the link below to set your password:\n\n{url}\n\n"
        f"This link will expire in {getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600)//60} minutes.\n"
    )
    send_mail(subject, message, getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@emdc.local"), [user.username])

    return Response({"detail": "Set-password email sent."}, status=status.HTTP_200_OK)


# 2) Public “Forgot Password”
@api_view(["POST"])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    Body: { "username": "<email>" }
    If the user exists, send a reset link. Always return 200 (no user enumeration).
    """
    username = request.data.get("username")
    if username:
        try:
            user = User.objects.get(username=username)
            url = build_set_password_url(user)
            subject = "Reset your password"
            message = (
                f"Hello,\n\n"
                f"Please click the link below to reset your password:\n\n{url}\n\n"
                f"This link will expire in {getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600)//60} minutes.\n"
            )
            send_mail(subject, message, getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@emdc.local"), [user.username])
        except User.DoesNotExist:
            pass
    return Response({"detail": "If the email exists, a reset link has been sent."}, status=status.HTTP_200_OK)


# 3) Frontend can validate token before showing the set-password form
@api_view(["POST"])
@permission_classes([AllowAny])
def validate_password_token(request):
    """
    Body: { "uid": "<uidb64>", "token": "<token>" }
    """
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    if not uidb64 or not token:
        return Response({"detail": "uid and token are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response({"detail": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)

    if default_token_generator.check_token(user, token):
        return Response({"detail": "Token valid."}, status=status.HTTP_200_OK)
    return Response({"detail": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)


# 4) Complete password set/reset
@api_view(["POST"])
@permission_classes([AllowAny])
def complete_password_set(request):
    """
    Body: { "uid": "<uidb64>", "token": "<token>", "password": "<new_password>" }
    Enforces Django's password validators.
    """
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    password = request.data.get("password")

    if not uidb64 or not token or not password:
        return Response({"detail": "uid, token, and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response({"detail": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response({"detail": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from django.contrib.auth.password_validation import validate_password
        validate_password(password, user=user)  # uses AUTH_PASSWORD_VALIDATORS
    except Exception as e:
        return Response({"password": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(password)
    user.save()
    return Response({"detail": "Password has been set."}, status=status.HTTP_200_OK)
