from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError

# --- Added for password reset flow ---
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

# NOTE: this import path matches THIS folder's serializer
from .serializers import UserSerializer

# --- Added utility for sending set-password emails ---
from .utils import send_set_password_email

# If you use role lookups elsewhere, keep your import the same:
from ..views.Maps.MapUserToRole import get_role

# === Added imports for shared-password fallback login ===
from django.contrib.auth.hashers import check_password
from ..models import RoleSharedPassword, MapUserToRole


# -----------------------
# User queries / auth
# -----------------------

@api_view(["GET"])
def user_by_id(request, user_id):
    user = get_object_or_404(User, id=user_id)
    serializer = UserSerializer(instance=user)
    return Response({"user": serializer.data}, status=status.HTTP_200_OK)


@api_view(["POST"])
def login(request):
    """
    Login rules (superset of original behavior):
      - Try per-user password first (original behavior).
      - If user has Organizer (2) or Judge (3) role, also accept the GLOBAL shared password.
    """
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"detail": "username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, username=username)

    # 1) Original behavior: check per-user password
    if user.check_password(password):
        token, _ = Token.objects.get_or_create(user=user)
        userSerializer = UserSerializer(instance=user)
        return Response(
            {"token": token.key, "user": userSerializer.data, "role": get_role(user.id)},
            status=status.HTTP_200_OK
        )

    # 2) New: shared-password fallback for roles 2 (Organizer) and 3 (Judge)
    role_map = MapUserToRole.objects.filter(uuid=user.id).first()
    if role_map and role_map.role in [2, 3]:
        shared = RoleSharedPassword.objects.filter(role=role_map.role).first()
        if shared and check_password(password, shared.password_hash):
            token, _ = Token.objects.get_or_create(user=user)
            userSerializer = UserSerializer(instance=user)
            return Response(
                {"token": token.key, "user": userSerializer.data, "role": get_role(user.id)},
                status=status.HTTP_200_OK
            )

    # If neither matched keep your original 404 contract
    return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
def signup(request):
    """
    Public sign-up. Preserves your original semantics:
      - If username exists: return existing user's data with token=None.
      - Otherwise create user, set password, create token.
    Additionally enables optional set-password emails (send_email=True by default).
    """
    try:
        user_data = request.data
        result = create_user(user_data, send_email=True, enforce_unusable_password=False)
        return Response(result, status=status.HTTP_201_CREATED)
    except ValidationError as e:
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["DELETE"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_user_by_id(request, user_id):
    delete_user(user_id)
    return Response({"detail": "User deleted successfully."}, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def edit_user(request):
    """
    Allows changing username (email) and/or password for the current user.
    Keeps your behavior (email uniqueness check; set_password on provided value),
    but avoids comparing raw text to hashed password.
    """
    user = get_object_or_404(User, id=request.data["id"])

    # Update username (email)
    new_username = request.data.get("username")
    if new_username and new_username != user.username:
        if User.objects.filter(username=new_username).exists():
            return Response({"detail": "Email already taken."}, status=status.HTTP_400_BAD_REQUEST)
        user.username = new_username

    # Update password (only if provided)
    new_password = request.data.get("password")
    if new_password:
        user.set_password(new_password)

    user.save()
    serializer = UserSerializer(instance=user)
    return Response({"user": serializer.data})


@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def test_token(request):
    return Response({"passed for {}".format(request.user.username)})


# -----------------------
# Creation / deletion helpers
# -----------------------

def create_user(user_data, send_email: bool = True, enforce_unusable_password: bool = False):
    """
    Shared helper used by admin/organizer/judge creation and public signup.

    Preserves your original behavior:
      - If a user with username exists, return existing user data with token=None.

    Adds optional features:
      - send_email: send set-password email after creation.
      - enforce_unusable_password: set an unusable password (e.g., for shared-role logins).
    """
    username = user_data.get("username")
    password = user_data.get("password")

    # Preserve original: if existing user, return data instead of error
    existing_user = User.objects.filter(username=username).first()
    if existing_user:
        serializer = UserSerializer(instance=existing_user)
        return {"token": None, "user": serializer.data}

    serializer = UserSerializer(data={"username": username, "password": password})
    if serializer.is_valid():
        with transaction.atomic():
            user = serializer.save()

            if enforce_unusable_password:
                user.set_unusable_password()
            else:
                # Keep original behavior: set whatever password was provided (no new strictness)
                if password:
                    user.set_password(password)
                else:
                    # If no password given, make it unusable (safe default)
                    user.set_unusable_password()

            user.save()
            token = Token.objects.create(user=user)

            if send_email:
                try:
                    send_set_password_email(user)
                except Exception as e:
                    # Do not fail creation if email fails (useful in dev)
                    print(f"[WARN] Failed to send set-password email: {e}")

            # Return serialized new user (match original return structure)
            return {"token": token.key, "user": UserSerializer(instance=user).data}

    raise ValidationError(serializer.errors)


def delete_user(uuid):
    user_to_delete = get_object_or_404(User, id=uuid)
    user_to_delete.delete()


# -----------------------
# Password reset endpoints
# -----------------------

@api_view(["POST"])
def forgot_password(request):
    """
    Trigger a reset email to the user.
    Payload: { "email": "<user-email>" }
    """
    email = request.data.get("email")
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(username=email)
    except User.DoesNotExist:
        # Do not reveal whether a user exists
        return Response({"detail": "If this email exists, a reset link has been sent."}, status=status.HTTP_200_OK)

    send_set_password_email(user)
    return Response({"detail": "If this email exists, a reset link has been sent."}, status=status.HTTP_200_OK)


@api_view(["POST"])
def password_reset_confirm(request):
    """
    Finalizes setting a new password.
    Payload:
      {
        "uid": "<base64 user id>",
        "token": "<token from email>",
        "new_password": "<new password>"
      }
    """
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    new_password = request.data.get("new_password")

    if not uidb64 or not token or not new_password:
        return Response({"detail": "uid, token and new_password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response({"detail": "Invalid link."}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({"detail": "Password has been set successfully."}, status=status.HTTP_200_OK)
