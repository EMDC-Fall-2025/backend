from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.hashers import make_password
from ..models import RoleSharedPassword

@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def set_shared_password(request):
    """
    Admin sets/overwrites the GLOBAL shared password for a role.
    Body:
      {
        "role": 2 or 3,   # 2=Organizer, 3=Judge
        "password": "new-shared-pass"
      }
    """
    role = request.data.get("role")
    password = request.data.get("password")

    if role not in [2, 3]:
        return Response({"error": "role must be 2 (Organizer) or 3 (Judge)."}, status=400)
    if not password:
        return Response({"error": "password is required."}, status=400)

    hashed = make_password(password)
    entry, created = RoleSharedPassword.objects.update_or_create(
        role=role,
        defaults={"password_hash": hashed}
    )
    return Response({
        "success": True,
        "role": role,
        "created": created,
        "message": "Shared password set successfully."
    }, status=200)
