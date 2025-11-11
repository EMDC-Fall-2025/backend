from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.hashers import make_password
from django.db import transaction
from ..models import RoleSharedPassword

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
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

    # Ensure role is an integer
    try:
        role = int(role)
    except (TypeError, ValueError):
        return Response({"error": "role must be 2 (Organizer) or 3 (Judge)."}, status=400)

    if role not in [2, 3]:
        return Response({"error": "role must be 2 (Organizer) or 3 (Judge)."}, status=400)
    if not password:
        return Response({"error": "password is required."}, status=400)

    # Use database transaction to ensure atomic replacement
    with transaction.atomic():
        # Delete ALL existing entries for this role to ensure complete replacement
        RoleSharedPassword.objects.filter(role=role).delete()
        
        # Verify deletion actually happened
        remaining_count = RoleSharedPassword.objects.filter(role=role).count()
        if remaining_count > 0:
            return Response({
                "error": f"Failed to delete old entries. {remaining_count} entries still exist for role {role}",
                "detail": "Please contact support."
            }, status=500)
        
        # Create new entry with the new password hash
        hashed = make_password(password)
        RoleSharedPassword.objects.create(
            role=role,
            password_hash=hashed
        )
        
        # Verify only one entry exists for this role
        count = RoleSharedPassword.objects.filter(role=role).count()
        if count != 1:
            return Response({
                "error": f"Database inconsistency: found {count} entries for role {role}",
                "detail": "Please contact support."
            }, status=500)
    
    return Response({
        "success": True,
        "role": role,
        "message": "Shared password set successfully."
    }, status=200)
