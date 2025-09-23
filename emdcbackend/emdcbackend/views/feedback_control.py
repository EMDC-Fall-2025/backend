from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404

from ..models import FeedbackDisplaySettings, Contest, SelectedFeedback, Scoresheet, MapScoresheetToTeamJudge, Judge, Teams, MapContestToTeam
from ..serializers import FeedbackDisplaySettingsSerializer, SelectedFeedbackSerializer

@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_feedback_display_settings(request, contest_id):
    """
    Get feedback display settings for a specific contest.
    If no settings exist, return default settings.
    """
    try:
        settings = FeedbackDisplaySettings.objects.get(contestid=contest_id)
        serializer = FeedbackDisplaySettingsSerializer(settings)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except FeedbackDisplaySettings.DoesNotExist:
        # Return default settings if none exist
        default_settings = {
            "contestid": contest_id,
            "show_presentation_comments": True,
            "show_journal_comments": True,
            "show_machinedesign_comments": True,
            "show_redesign_comments": True,
            "show_championship_comments": True,
            "show_penalty_comments": False,
        }
        return Response(default_settings, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_feedback_display_settings(request):
    """
    Create feedback display settings for a contest.
    """
    try:
        # Verify contest exists
        contest = get_object_or_404(Contest, id=request.data["contestid"])
        
        # Check if settings already exist
        if FeedbackDisplaySettings.objects.filter(contestid=request.data["contestid"]).exists():
            return Response(
                {"error": "Feedback display settings already exist for this contest. Use PUT to update."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = FeedbackDisplaySettingsSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_feedback_display_settings(request):
    """
    Update feedback display settings for a contest.
    """
    try:
        settings = get_object_or_404(FeedbackDisplaySettings, contestid=request.data["contestid"])
        serializer = FeedbackDisplaySettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["DELETE"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_feedback_display_settings(request, contest_id):
    """
    Delete feedback display settings for a contest.
    """
    try:
        settings = get_object_or_404(FeedbackDisplaySettings, contestid=contest_id)
        settings.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_all_feedback_display_settings(request):
    """
    Get feedback display settings for all contests.
    """
    try:
        settings = FeedbackDisplaySettings.objects.all()
        serializer = FeedbackDisplaySettingsSerializer(settings, many=True)
        return Response({"settings": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def get_feedback_display_settings_for_contest(contest_id):
    """
    Helper function to get feedback display settings for a contest.
    Returns default settings if none exist.
    """
    try:
        settings = FeedbackDisplaySettings.objects.get(contestid=contest_id)
        return {
            "show_presentation_comments": settings.show_presentation_comments,
            "show_journal_comments": settings.show_journal_comments,
            "show_machinedesign_comments": settings.show_machinedesign_comments,
            "show_redesign_comments": settings.show_redesign_comments,
            "show_championship_comments": settings.show_championship_comments,
            "show_penalty_comments": settings.show_penalty_comments,
        }
    except FeedbackDisplaySettings.DoesNotExist:
        # Return default settings
        return {
            "show_presentation_comments": True,
            "show_journal_comments": True,
            "show_machinedesign_comments": True,
            "show_redesign_comments": True,
            "show_championship_comments": True,
            "show_penalty_comments": False,
        }

# New endpoints for granular feedback control

@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_all_feedback_for_contest(request, contest_id):
    """Get all feedback comments for a contest with judge and team information"""
    try:
        # Get all scoresheets for teams in this contest
        contest_teams = MapContestToTeam.objects.filter(contestid=contest_id).values_list('teamid', flat=True)
        scoresheet_mappings = MapScoresheetToTeamJudge.objects.filter(teamid__in=contest_teams)
        scoresheet_ids = scoresheet_mappings.values_list('scoresheetid', flat=True)
        
        # Get scoresheets with comments
        scoresheets = Scoresheet.objects.filter(
            id__in=scoresheet_ids,
            field9__isnull=False
        ).exclude(field9__exact='')
        
        feedback_data = []
        for sheet in scoresheets:
            # Get judge and team info
            mapping = scoresheet_mappings.filter(scoresheetid=sheet.id).first()
            if mapping:
                judge = Judge.objects.filter(id=mapping.judgeid).first()
                team = Teams.objects.filter(id=mapping.teamid).first()
                
                feedback_data.append({
                    "scoresheet_id": sheet.id,
                    "comment": sheet.field9,
                    "sheet_type": sheet.sheetType,
                    "sheet_type_name": sheet.get_sheetType_display(),
                    "judge_name": f"{judge.first_name} {judge.last_name}" if judge else "Unknown Judge",
                    "judge_id": mapping.judgeid,
                    "team_name": team.team_name if team else "Unknown Team",
                    "team_id": mapping.teamid,
                })
        
        return Response({"feedback": feedback_data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_selected_feedback_for_contest(request, contest_id):
    """Get which feedback comments are selected for display"""
    try:
        selected_feedback = SelectedFeedback.objects.filter(contestid=contest_id)
        serializer = SelectedFeedbackSerializer(selected_feedback, many=True)
        return Response({"selected_feedback": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_selected_feedback(request):
    """Update which feedback comments are selected for display"""
    try:
        contest_id = request.data.get("contest_id")
        selected_scoresheet_ids = request.data.get("selected_scoresheet_ids", [])
        
        if not contest_id:
            return Response({"error": "contest_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Clear existing selections for this contest
        SelectedFeedback.objects.filter(contestid=contest_id).delete()
        
        # Create new selections
        for scoresheet_id in selected_scoresheet_ids:
            SelectedFeedback.objects.create(
                contestid=contest_id,
                scoresheet_id=scoresheet_id,
                is_selected=True
            )
        
        return Response({"message": "Selected feedback updated successfully"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
