from rest_framework import status
from rest_framework.decorators import (
  api_view,
  authentication_classes,
  permission_classes,
)
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404
from ...models import MapContestToOrganizer, Organizer, Contest, MapUserToRole
from ...serializers import MapContestToOrganizerSerializer, ContestSerializer, OrganizerSerializer

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_contest_organizer_mapping(request):
    try:
        map_data = request.data
        result = map_contest_to_organizer(map_data)
        return Response(result, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def map_contest_to_organizer(map_data):
    serializer = MapContestToOrganizerSerializer(data=map_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data
    else:
        raise ValidationError(serializer.errors)

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_organizers_by_contest_id(request, contest_id):
  organizer_ids = MapContestToOrganizer.objects.filter(contestid=contest_id)
  organizers = Organizer.objects.filter(id__in=organizer_ids)
  serializer = OrganizerSerializer(organizers, many=True)
  return Response({"Organizers": serializer.data},status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_contests_by_organizer_id(request,organizer_id):
  # Check if user is an admin (admins can access any organizer's contests)
  is_admin = MapUserToRole.objects.filter(
    uuid=request.user.id,
    role=MapUserToRole.RoleEnum.ADMIN
  ).exists()
  
  # If not admin, verify user is requesting their own organizer ID
  if not is_admin:
    # First check if user is an organizer at all
    user_organizer_mapping = MapUserToRole.objects.filter(
      uuid=request.user.id,
      role=MapUserToRole.RoleEnum.ORGANIZER
    ).first()
    
    if not user_organizer_mapping:
      return Response(
        {"detail": "You must be an organizer to access this resource."},
        status=status.HTTP_403_FORBIDDEN
      )
    
    # Then verify the organizer_id matches the user's organizer ID
    if user_organizer_mapping.relatedid != organizer_id:
      return Response(
        {"detail": f"You do not have permission to access organizer {organizer_id}'s contests. Your organizer ID is {user_organizer_mapping.relatedid}."},
        status=status.HTTP_403_FORBIDDEN
      )
  
  mappings = MapContestToOrganizer.objects.filter(organizerid=organizer_id)
  contest_ids = mappings.values_list('contestid',flat=True)
  contests = Contest.objects.filter(id__in=contest_ids)
  serializer = ContestSerializer(contests, many=True)
  return Response({"Contests":serializer.data},status=status.HTTP_200_OK)

@api_view(["DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_contest_organizer_mapping(request, organizer_id, contest_id):
    map_to_delete = get_object_or_404(MapContestToOrganizer, organizerid=organizer_id, contestid=contest_id)
    map_to_delete.delete()
    return Response({"detail": "Contest To Organizer Mapping deleted successfully."}, status=status.HTTP_200_OK)


from collections import defaultdict

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_all_contests_by_organizer(request):
    try:
        # Create a dictionary with organizer_id as key and a list of contests as the value
        contests_by_organizer = defaultdict(list)

        # Get all contest-organizer mappings
        mappings = MapContestToOrganizer.objects.all()

        # Iterate through mappings and group contests by organizer
        for mapping in mappings:
            organizer_id = mapping.organizerid
            contest_id = mapping.contestid
            try:
                contest = Contest.objects.get(id=contest_id)
                contests_by_organizer[organizer_id].append(contest)
            except Contest.DoesNotExist:
                # Skip if contest doesn't exist
                continue

        # Get all organizers
        organizers = Organizer.objects.all()

        # Include all organizers in the final result
        organizer_contests = {}
        for organizer in organizers:
            # If the organizer has no contests, include them with an empty list
            contests = contests_by_organizer.get(organizer.id, [])
            organizer_contests[organizer.id] = ContestSerializer(contests, many=True).data

        return Response(organizer_contests, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_organizer_names_by_contests(request):
    try:
        # Optimized query: Get all contest-organizer mappings with organizer names in one query
        mappings_with_names = MapContestToOrganizer.objects.select_related('organizerid').values(
            'contestid',
            'organizerid__first_name',
            'organizerid__last_name'
        )

        # Group organizers by contest
        contests_with_organizers = defaultdict(list)
        for mapping in mappings_with_names:
            contest_id = mapping['contestid']
            first_name = mapping['organizerid__first_name']
            last_name = mapping['organizerid__last_name']
            if first_name and last_name:  # Ensure names exist
                full_name = f"{first_name} {last_name}"
                contests_with_organizers[contest_id].append(full_name)

        # Get all contests (including those without organizers)
        contests = Contest.objects.all()

        # Ensure every contest is in the final result (even those with no organizers)
        contest_organizer_mapping = {}
        for contest in contests:
            contest_id = contest.id
            contest_organizer_mapping[contest_id] = contests_with_organizers.get(contest_id, [])

        return Response(contest_organizer_mapping, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# endpoint that returns all the contests and their organizers
# key: contestid, value: list of organizer objects

