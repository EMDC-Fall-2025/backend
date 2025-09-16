from django.core.exceptions import FieldError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from ...models import SpecialAward
from ...serializers import SpecialAwardSerializer
# FILE OVERVIEW: This file contains all views associated with the special awards URLs

# POST request to create a new award team map
# Accepts JSON data if data is valid create map if not return 400/500 error 
@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_award_team_mapping(request):
    try:
        serializer = SpecialAwardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# GET request to get award_id by team_id
# Gets all award maps associated with a given team_id returns JSON or 500 if no awards found 
@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_award_id_by_team_id(request, team_id):
    try:
        awards = SpecialAward.objects.filter(teamid=team_id)
        serializer = SpecialAwardSerializer(awards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Delete award map by team_ID and award_name accepts these as URL params
# If it deletes properly 204 if not 404/500 code 
@api_view(["DELETE"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_award_team_mapping_by_id(request, team_id, award_name):
    try:
        award = SpecialAward.objects.get(teamid=team_id, award_name=award_name)
        award.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except SpecialAward.DoesNotExist:
        return Response({"error": "Award not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# PUT request for updating an award map
# accepts team_id and award_name as url params
# If valid 200 if not 400/404/500 code 
@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_award_team_mapping(request, team_id, award_name):
    try:
        award = SpecialAward.objects.get(teamid=team_id, award_name=award_name)
        serializer = SpecialAwardSerializer(award, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except SpecialAward.DoesNotExist:
        return Response({"error": "Award not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# GET request that returns all awards
@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_all_awards(request):
    try:
        award = SpecialAward.objects.all()
        serializer = SpecialAwardSerializer(award, many=True)
        return Response({"awards": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# Get request to get get all awards based on isJudge boolean
# used in frontend pages for organizers and judge only show their respective awards
@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_awards_by_role(request, isJudge):
    try:
        is_judge = isJudge.lower() == 'true'
        awards = SpecialAward.objects.filter(isJudge=is_judge)
        serializer = SpecialAwardSerializer(awards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)