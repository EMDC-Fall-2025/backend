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

from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

# NOTE: this import path matches THIS folder's new serializer
from .serializers import UserSerializer
from .utils import send_set_password_email

# If you use role lookups elsewhere, keep your import the same:
from ..views.Maps.MapUserToRole import get_role


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
    user = get_object_or_404(User, username=request.data["username"])
    if not user.check_password(request.data["password"]):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    token, _ = Token.objects.get_or_create(user=user)
    userSerializer = UserSerializer(instance=user)
    return Response({"token": token.key, "user": userSerializer.data, "role": get_role(user.id)})


@api_view(["POST"])
def signup(request):
    """
    Public sign-up. Creates a user with the provided password.
    (If you want to force email verification before login, that can be added later.)
    """
    try:
        user_data = request.data
        result = create_user(user_data)  # will also send set-password email
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
    """
    user = get_object_or_404(User, id=request.data["id"])

    # Update username (email)
    try:
        new_username = request.data.get("username")
        if new_username and new_username != user.username:
            if User.objects.filter(username=new_username).exists():
                return Response({"detail": "Email already taken."}, status=status.HTTP_400_BAD_REQUEST)
            user.username = new_username
    except Exception:
        pass

    # Update password
    try:
        new_password = request.data.get("password")
        if new_password:
            user.set_password(new_password)
    except Exception:
        pass

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

def create_user(user_data):
    """
    Shared helper used by admin/organizer/judge creation and public signup.
    We:
      - create the user
      - set the password provided
      - create a token
      - send a set-password email so the user can redefine it (requested behavior)
    """
    username = user_data.get("username")
    password = user_data.get("password")

    if not username:
        raise ValidationError("Username (email) is required.")
    if User.objects.filter(username=username).exists():
        raise ValidationError("Username already exists.")

    serializer = UserSerializer(data={"username": username, "password": password})
    if serializer.is_valid():
        with transaction.atomic():
            user = serializer.save()
            # enforce min length 8 here for safety (backend validation)
            if not password or len(password) < 8:
                # If a too-short or blank password was provided, set an unusable one
                user.set_unusable_password()
            else:
                user.set_password(password)
            user.save()

            token = Token.objects.create(user=user)

            # Always send a "set your password" email on creation (per your request)
            try:
                send_set_password_email(user)
            except Exception as e:
                # Don't fail user creation if email send fails in dev
                print(f"[WARN] Failed to send set-password email: {e}")

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

    if len(new_password) < 8:
        return Response({"detail": "Password must be at least 8 characters."}, status=status.HTTP_400_BAD_REQUEST)

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
