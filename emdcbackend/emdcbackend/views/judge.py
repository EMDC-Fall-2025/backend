from django.db import transaction
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
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from .Maps.MapUserToRole import create_user_role_map
from .Maps.MapContestToJudge import create_contest_to_judge_map
from .Maps.MapClusterToJudge import map_cluster_to_judge
from .scoresheets import create_sheets_for_teams_in_cluster, delete_sheets_for_teams_in_cluster
from ..auth.views import create_user
from ..models import Judge, Scoresheet, MapScoresheetToTeamJudge, MapJudgeToCluster, Teams, MapContestToJudge, MapUserToRole
from django.db.models import Count
from ..serializers import JudgeSerializer
from ..auth.serializers import UserSerializer
from ..models import ScoresheetEnum

@api_view(["GET"])
def judge_by_id(request, judge_id):  # Consistent parameter name
    judge = get_object_or_404(Judge, id=judge_id) 
    serializer = JudgeSerializer(instance=judge)
    return Response({"Judge": serializer.data}, status=status.HTTP_200_OK)



@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_judge(request):
    try:
        with transaction.atomic():
            user_response, judge_response = create_user_and_judge(request.data)

            # Check for existing mappings and clean up before creating new ones
            judge_id = judge_response.get("id")

            # Map judge to user and contest
            responses = [
                create_user_role_map({
                    "uuid": user_response.get("user").get("id"),
                    "role": 3,
                    "relatedid": judge_response.get("id")
                }),
                create_contest_to_judge_map({
                    "contestid": request.data["contestid"],
                    "judgeid": judge_response.get("id")
                }),
                map_cluster_to_judge({
                    "judgeid": judge_response.get("id"),
                    "clusterid": request.data["clusterid"]
                })
            ]

            # Check for any errors in mapping responses
            for response in responses:
                if isinstance(response, Response):
                    return response

            # Try to create score sheets for teams in cluster (if any teams exist)
            score_sheets_response = []
            try:
                score_sheets_response = create_sheets_for_teams_in_cluster(
                    judge_response.get("id"),
                    request.data["clusterid"],
                    request.data["presentation"],
                    request.data["journal"],
                    request.data["mdo"],
                    request.data["runpenalties"],
                    request.data["otherpenalties"],
                    request.data["redesign"],
                    request.data["championship"],
                )
            except ValidationError as e:
                # If no teams in cluster, that's okay - judge can still be created
                # Score sheets will be created when teams are added to the cluster
                score_sheets_response = []

            return Response({
                "user": user_response,
                "judge": judge_response,
                "user_map": responses[0],
                "contest_map": responses[1],
                "cluster_map": responses[2],
                "score_sheets": score_sheets_response
            }, status=status.HTTP_201_CREATED)

    except ValidationError as e:  # Catching ValidationErrors specifically
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def edit_judge(request):
    try:
        judge = get_object_or_404(Judge, id=request.data["id"])
        
        # Get the current cluster ID before cleanup
        current_cluster_mapping = MapJudgeToCluster.objects.filter(judgeid=judge.id).first()
        current_cluster_id = current_cluster_mapping.clusterid if current_cluster_mapping else None
        
        # Clean up any existing duplicate mappings for this judge
        with transaction.atomic():
            # Clean up ALL existing cluster mappings for this judge
            MapJudgeToCluster.objects.filter(judgeid=judge.id).delete()
            
            # Clean up ALL existing user role mappings for this judge
            MapUserToRole.objects.filter(role=3, relatedid=judge.id).delete()
        new_first_name = request.data["first_name"]
        new_last_name = request.data["last_name"]
        new_phone_number = request.data["phone_number"]
        new_presentation = request.data["presentation"]
        new_mdo = request.data["mdo"]
        new_journal = request.data["journal"]
        new_championship = request.data["championship"]
        new_runpenalties = request.data["runpenalties"]
        new_otherpenalties = request.data["otherpenalties"]
        new_redesign = request.data["redesign"]
        new_cluster = request.data["clusterid"]
        new_username = request.data["username"]
        new_role = request.data["role"]
        with transaction.atomic():
            # Get the current cluster ID from the request data
            clusterid = new_cluster
            
            # Get the user from the username in request data
            user = get_object_or_404(User, username=new_username)
            if user.username != new_username:
                user.username = new_username
                user.save()
            user_serializer = UserSerializer(instance=user)
            # Update judge name details
            if new_first_name != judge.first_name:
                judge.first_name = new_first_name
            if new_last_name != judge.last_name:
                judge.last_name = new_last_name
            if new_phone_number != judge.phone_number:
                judge.phone_number = new_phone_number
            if new_role != judge.role:
                judge.role = new_role

            # Only recreate scoresheets if cluster has changed or scoresheet types have changed
            cluster_changed = current_cluster_id != new_cluster
            scoresheet_types_changed = (
                judge.presentation != new_presentation or
                judge.journal != new_journal or
                judge.mdo != new_mdo or
                judge.runpenalties != new_runpenalties or
                judge.otherpenalties != new_otherpenalties or
                judge.redesign != new_redesign or
                judge.championship != new_championship
            )
            
            # Also ensure scoresheets exist for judge in target cluster (e.g., if mappings were wiped earlier)
            from ..models import MapClusterToTeam, MapScoresheetToTeamJudge
            missing_scoresheets = False
            try:
                cluster_team_mappings = MapClusterToTeam.objects.filter(clusterid=new_cluster)
                team_ids = list(cluster_team_mappings.values_list('teamid', flat=True))
                if team_ids:
                    # Look for at least one mapping in this cluster for this judge
                    existing_cluster_mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge.id, teamid__in=team_ids)
                    missing_scoresheets = not existing_cluster_mappings.exists()
            except Exception:
                # If any lookup fails, fall back to not missing
                missing_scoresheets = False

            should_delete = cluster_changed or scoresheet_types_changed
            if should_delete:
                # Delete all existing scoresheets for this judge (from current cluster)
                if current_cluster_id:
                    delete_sheets_for_teams_in_cluster(
                        judge.id,
                        current_cluster_id,
                        judge.presentation,
                        judge.journal,
                        judge.mdo,
                        judge.runpenalties,
                        judge.otherpenalties,
                        judge.redesign,
                        judge.championship,
                    )

            if should_delete or missing_scoresheets:
                # Create new blank scoresheets (either after delete or if missing)
                create_sheets_for_teams_in_cluster(
                    judge.id,
                    new_cluster,
                    new_presentation,
                    new_journal,
                    new_mdo,
                    new_runpenalties,
                    new_otherpenalties,
                    new_redesign,
                    new_championship,
                )

            # Always ensure cluster-judge mapping exists
            map_cluster_to_judge({
                "judgeid": judge.id,
                "clusterid": new_cluster
            })
            
            # Ensure contest-judge mapping exists (some flows may lack it)
            try:
                from ..models import MapContestToJudge
                if not MapContestToJudge.objects.filter(judgeid=judge.id, contestid=judge.contestid).exists():
                    from .Maps.MapContestToJudge import create_contest_to_judge_map
                    create_contest_to_judge_map({
                        "contestid": judge.contestid,
                        "judgeid": judge.id,
                    })
            except Exception:
                pass
            
            # Create new user-role mapping
            create_user_role_map({
                "uuid": user.id,
                "role": 3,
                "relatedid": judge.id
            })

            # Update the boolean values (always update to match request data)
            judge.presentation = new_presentation
            judge.mdo = new_mdo
            judge.journal = new_journal
            judge.runpenalties = new_runpenalties
            judge.otherpenalties = new_otherpenalties
            judge.redesign = new_redesign
            judge.championship = new_championship



            judge.save()

        serializer = JudgeSerializer(instance=judge)
    
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({"judge": serializer.data, "clusterid": clusterid, "user": user_serializer.data}, status=status.HTTP_200_OK)

@api_view(["DELETE"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_judge(request, judge_id):
    try:
        with transaction.atomic():
            judge = get_object_or_404(Judge, id=judge_id)
            
            # Get all related data
            scoresheet_mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id)
            scoresheet_ids = scoresheet_mappings.values_list('scoresheetid', flat=True)
            scoresheets = Scoresheet.objects.filter(id__in=scoresheet_ids)
            user_mappings = MapUserToRole.objects.filter(role=3, relatedid=judge_id)
            cluster_mappings = MapJudgeToCluster.objects.filter(judgeid=judge_id)
            contest_mappings = MapContestToJudge.objects.filter(judgeid=judge_id)
            
            # Get user if exists
            user = None
            if user_mappings.exists():
                user_id = user_mappings.first().uuid
                try:
                    user = get_object_or_404(User, id=user_id)
                except User.DoesNotExist:
                    user = None

            # Delete all associated scoresheets
            for scoresheet in scoresheets:
                scoresheet.delete()

            # Delete all scoresheet mappings
            for mapping in scoresheet_mappings:
                mapping.delete()

            # Delete all contest mappings
            for mapping in contest_mappings:
                mapping.delete()

            # Delete all cluster mappings
            for mapping in cluster_mappings:
                mapping.delete()

            # Delete all user role mappings
            for mapping in user_mappings:
                mapping.delete()

            # Delete associated user
            if user:
                user.delete()

            # Finally, delete the judge
            judge.delete()

        return Response({"detail": "Judge deleted successfully."}, status=status.HTTP_200_OK)
    
    except ValidationError as e:  # Catching ValidationErrors specifically
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def create_judge_instance(judge_data):
    """
    Create a judge instance in the database.
    Validates judge data and saves to database.
    """
    # Check if a judge with the same name already exists
    existing_judge = Judge.objects.filter(
        first_name=judge_data["first_name"],
        last_name=judge_data["last_name"]
    ).first()
    
    if existing_judge:
        # Return the existing judge data instead of creating a new one
        serializer = JudgeSerializer(instance=existing_judge)
        return serializer.data
    
    serializer = JudgeSerializer(data=judge_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data
    raise ValidationError(serializer.errors)


def create_user_and_judge(data):
    """
    Create both user account and judge profile for a new judge.
    Handles the complete user registration process including authentication setup.
    """
    # Create user account for authentication
    user_data = {"username": data["username"], "password": data["password"]}
    user_response = create_user(user_data)
    if not user_response.get('user'):
        raise ValidationError('User creation failed.')
    
    # Create judge profile with contest-specific data
    judge_data = {
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "phone_number": data["phone_number"],
        "contestid": data["contestid"],
        "presentation": data.get("presentation", False),
        "mdo": data.get("mdo", False),
        "journal": data.get("journal", False),
        "runpenalties": data.get("runpenalties", False),
        "otherpenalties": data.get("otherpenalties", False),
        "redesign": data.get("redesign", False),
        "championship": data.get("championship", False),
        "role": data.get("role", 3)
    }
    judge_response = create_judge_instance(judge_data)
    if not judge_response.get('id'):  # If judge creation fails, raise an exception
        raise ValidationError('Judge creation failed.')
    return user_response, judge_response


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def are_all_score_sheets_submitted(request):
    """
    Check if all score sheets assigned to a list of judges are submitted.
    Expects a JSON body with a list of judge objects.
    """
    judges = request.data

    if not judges:
        return Response(
            {"detail": "No judges provided."},
            status=status.HTTP_400_BAD_REQUEST
        )

    results = {}

    # Iterate over each judge object in the list
    for judge in judges:
        judge_id = judge.get('id')
        mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id)

        if not mappings.exists():
            results[judge_id] = False
            continue

        required_sheet_ids = [
            m.scoresheetid for m in mappings
            if m.sheetType not in (ScoresheetEnum.RUNPENALTIES, ScoresheetEnum.OTHERPENALTIES)
        ]

        if not required_sheet_ids:
            results[judge_id] = True
            continue

        all_submitted = not Scoresheet.objects.filter(
            id__in=required_sheet_ids,
            isSubmitted=False
        ).exists()

        results[judge_id] = all_submitted

    return Response(results, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def judge_disqualify_team(request):
     team = get_object_or_404(Teams, id=request.data["teamid"])
     team.judge_disqualified = request.data["judge_disqualified"]
     team.save()
     return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
def get_all_judges(request):
    """Get all judges"""
    try:
        judges = Judge.objects.all()
        serializer = JudgeSerializer(judges, many=True)
        return Response({"Judges": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)