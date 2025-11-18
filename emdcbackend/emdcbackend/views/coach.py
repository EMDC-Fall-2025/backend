from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from ..auth.views import create_user
from ..models import Coach
from ..serializers import CoachSerializer
from rest_framework.exceptions import ValidationError
from ..models import MapUserToRole
from ..auth.views import User, delete_user_by_id
from ..auth.utils import send_set_password_email
from django.contrib.sessions.models import Session

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def coach_by_id(request, coach_id):
  coach = get_object_or_404(Coach, id = coach_id)
  serializer = CoachSerializer(instance=coach)
  return Response({"Coach": serializer.data}, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def coach_get_all(request):
  coaches = Coach.objects.all()
  serializer = CoachSerializer(coaches, many=True)
  return Response({"Coaches":serializer.data}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_coach(request):
    serializer = CoachSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"coach": serializer.data},status=status.HTTP_200_OK)
    return Response(
        serializer.errors, status=status.HTTP_400_BAD_REQUEST
    )

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def edit_coach(request):
    coach = get_object_or_404(Coach, id=request.data["id"])
    coach.first_name = request.data["first_name"]
    coach.last_name = request.data["last_name"]
    coach.school_name = request.data["school_name"]
    coach.save()

    serializer = CoachSerializer(instance=coach)
    return Response({"coach": serializer.data}, status=status.HTTP_200_OK)

def _delete_user_sessions(user_id: int) -> None:
    """
    Proactively invalidate all active sessions for the given user id.
    This ensures any existing session cookies become unusable immediately.
    """
    try:
        for session in Session.objects.all():
            data = session.get_decoded()
            if str(data.get("_auth_user_id")) == str(user_id):
                session.delete()
    except Exception:
        pass


@api_view(["DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_coach(request, coach_id):
    try:
        coach = get_object_or_404(Coach, id=coach_id)
        coach_mapping = MapUserToRole.objects.get(role=MapUserToRole.RoleEnum.COACH, coachid=coach_id)
        user_id = coach_mapping.userid
        
        # Invalidate all active sessions for this user before deleting user
        _delete_user_sessions(user_id)
        
        coach.delete()
        coach_mapping.delete()
        delete_user_by_id(request, user_id)
        return Response({"Detail": "Coach deleted successfully."}, status=status.HTTP_200_OK)
    except Coach.DoesNotExist:
        return Response({"error": "Coach not found."}, status=status.HTTP_404_NOT_FOUND)
    except MapUserToRole.DoesNotExist:
        return Response({"error": "Coach mapping not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def create_coach_instance(coach_data):
    serializer = CoachSerializer(data=coach_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data
    raise ValidationError("Coach creation failed")

def create_coach_only(data):
    coach_data = {
        "first_name": data["first_name"],
        "last_name": data.get("last_name", "") or ""  
    }
    coach_response = create_coach_instance(coach_data)
    if not coach_response.get('id'):
        raise ValidationError('Coach creation failed.')
    return coach_response

def create_user_and_coach(data):
    user_data = {"username": data["username"], "password": data["password"]}
    # Create user with unusable password - coach will set it via email link
    user_response = create_user(user_data, send_email=False, enforce_unusable_password=True)
    if not user_response.get('user'):
        raise ValidationError('User creation failed.')
    
    coach_data = {
        "first_name": data["first_name"],
        "last_name": data.get("last_name", "") or "",  
    }
    coach_response = create_coach_instance(coach_data)
    if not coach_response.get('id'): 
        raise ValidationError('Coach creation failed.')
    
    # Send set-password email to the coach
    user_id = user_response.get("user", {}).get("id")
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            send_set_password_email(user, subject="Set your EMDC Coach account password")
        except Exception as e:
            # Log error but don't fail coach creation if email fails
            print(f"[WARN] Failed to send set-password email to coach {user.username}: {e}")
    
    return user_response, coach_response

def get_coach(coach_id):
    coach = get_object_or_404(Coach, id = coach_id)
    serializer = CoachSerializer(instance=coach)
    return serializer.data

