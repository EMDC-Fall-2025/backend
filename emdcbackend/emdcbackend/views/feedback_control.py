from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from ..models import SelectedFeedback, Scoresheet, MapScoresheetToTeamJudge, Judge, Teams, MapContestToTeam
from ..serializers import SelectedFeedbackSerializer

"""Granular feedback control endpoints only (category toggles removed)."""

# Granular feedback control functions
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
    """Get currently selected feedback for a contest"""
    try:
        selected_feedback = SelectedFeedback.objects.filter(contestid=contest_id)
        serializer = SelectedFeedbackSerializer(selected_feedback, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_selected_feedback(request):
    """Update selected feedback for a contest"""
    try:
        contest_id = request.data.get('contest_id')
        selected_scoresheet_ids = request.data.get('selected_scoresheet_ids', [])
        
        if not contest_id:
            return Response({"error": "contest_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete existing selections for this contest
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

