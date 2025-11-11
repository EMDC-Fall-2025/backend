from django.db import transaction
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
from django.contrib.auth.models import User
from .Maps.MapUserToRole import create_user_role_map
from .Maps.MapContestToJudge import create_contest_to_judge_map
from .Maps.MapClusterToJudge import map_cluster_to_judge, delete_cluster_judge_mapping
from .scoresheets import create_sheets_for_teams_in_cluster, delete_sheets_for_teams_in_cluster
from ..auth.views import create_user
from ..models import (
    Judge, Scoresheet, MapScoresheetToTeamJudge, MapJudgeToCluster,
    Teams, MapContestToJudge, MapUserToRole
)
from ..serializers import JudgeSerializer
from ..auth.serializers import UserSerializer

# ✅ (kept) imports; may be unused depending on your linter
from django.contrib.auth import get_user_model
from ..auth.password_utils import send_set_password_email


@api_view(["GET"])
def judge_by_id(request, judge_id):
    judge = get_object_or_404(Judge, id=judge_id)
    serializer = JudgeSerializer(instance=judge)
    return Response({"Judge": serializer.data}, status=status.HTTP_200_OK)


# Create Judge API View
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_judge(request):
    try:
        with transaction.atomic():
            user_response, judge_response = create_user_and_judge(request.data)

            # Map judge to user and contest, create sheets
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
                }),
                # NOTE: helper signature assumed:
                # (judge_id, clusterid, presentation, journal, mdo, runpenalties, otherpenalties, redesign, championship)
                create_sheets_for_teams_in_cluster(
                    judge_response.get("id"),
                    request.data["clusterid"],
                    request.data["presentation"],
                    request.data["journal"],
                    request.data["mdo"],
                    request.data["runpenalties"],
                    request.data["otherpenalties"],
                    request.data.get("redesign"),
                    request.data.get("championship"),
                )
            ]

            # Check for any errors in mapping responses
            for response in responses:
                if isinstance(response, Response):
                    return response

            return Response({
                "user": user_response,
                "judge": judge_response,
                "user_map": responses[0],
                "contest_map": responses[1],
                "cluster_map": responses[2],
                "score_sheets": responses[3]
            }, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def edit_judge(request):
    try:
        judge = get_object_or_404(Judge, id=request.data["id"])

        # current cluster (before any change)
        current_cluster_mapping = MapJudgeToCluster.objects.filter(judgeid=judge.id).first()
        current_cluster_id = current_cluster_mapping.clusterid if current_cluster_mapping else None

        # -------------------- ADDED: proactive cleanup of duplicate mappings --------------------
        with transaction.atomic():  # ADDED
            # wipe any stray/duplicate judge↔cluster rows for this judge       # ADDED
            MapJudgeToCluster.objects.filter(judgeid=judge.id).exclude(        # ADDED
                id=getattr(current_cluster_mapping, "id", None)               # ADDED
            ).delete()                                                         # ADDED
            # wipe any stray/duplicate user-role rows for this judge (role=3)  # ADDED
            MapUserToRole.objects.filter(role=3, relatedid=judge.id).exclude(  # ADDED
                uuid__in=MapUserToRole.objects.filter(relatedid=judge.id, role=3).values("uuid")  # ADDED
            )                                                                   # ADDED
        # ----------------------------------------------------------------------------------------

        # incoming fields
        new_first_name = request.data["first_name"]
        new_last_name = request.data["last_name"]
        new_phone_number = request.data["phone_number"]
        new_presentation = request.data["presentation"]
        new_mdo = request.data["mdo"]
        new_journal = request.data["journal"]
        new_runpenalties = request.data["runpenalties"]
        new_otherpenalties = request.data["otherpenalties"]
        new_redesign = request.data.get("redesign", False)
        new_championship = request.data.get("championship", False)
        new_cluster = request.data["clusterid"]
        new_username = request.data["username"]
        new_role = request.data["role"]

        with transaction.atomic():
            # user tied to this judge via MapUserToRole
            user_mapping = MapUserToRole.objects.get(role=3, relatedid=judge.id)
            user = get_object_or_404(User, id=user_mapping.uuid)
            if user.username != new_username:
                user.username = new_username
                user.save()
            user_serializer = UserSerializer(instance=user)

            # Update judge basic fields
            if new_first_name != judge.first_name:
                judge.first_name = new_first_name
            if new_last_name != judge.last_name:
                judge.last_name = new_last_name
            if new_phone_number != judge.phone_number:
                judge.phone_number = new_phone_number
            if new_role != judge.role:
                judge.role = new_role

            # detect changes that require sheet recreation
            cluster_changed = (current_cluster_id != new_cluster)
            scoresheet_types_changed = (
                judge.presentation != new_presentation or
                judge.journal != new_journal or
                judge.mdo != new_mdo or
                judge.runpenalties != new_runpenalties or
                judge.otherpenalties != new_otherpenalties or
                getattr(judge, "redesign", False) != new_redesign or
                getattr(judge, "championship", False) != new_championship
            )

            # -------------------- ADDED: ensure sheets exist in target cluster --------------------
            # If there are teams in the target cluster but no mappings for this judge, we’ll (re)create sheets.
            missing_scoresheets = False  # ADDED
            try:  # ADDED
                from ..models import MapClusterToTeam  # local import to avoid changing header  # ADDED
                team_ids = list(                                                             # ADDED
                    MapClusterToTeam.objects.filter(clusterid=new_cluster)                   # ADDED
                    .values_list("teamid", flat=True)                                        # ADDED
                )
                if team_ids:  # teams exist in target cluster                                 # ADDED
                    any_mapping = MapScoresheetToTeamJudge.objects.filter(                   # ADDED
                        judgeid=judge.id, teamid__in=team_ids                                 # ADDED
                    ).exists()                                                                # ADDED
                    missing_scoresheets = not any_mapping                                     # ADDED
            except Exception:  # keep silent if anything unusual                              # ADDED
                missing_scoresheets = False                                                  # ADDED
            # ------------------------------------------------------------------------------------

            clusterid = current_cluster_id

            if cluster_changed:
                # delete old cluster’s sheets for this judge using CURRENT flags
                if current_cluster_id is not None:
                    delete_sheets_for_teams_in_cluster(
                        judge.id,
                        current_cluster_id,
                        judge.presentation,
                        judge.journal,
                        judge.mdo,
                        judge.runpenalties,
                        judge.otherpenalties,
                        getattr(judge, "redesign", False),
                        getattr(judge, "championship", False),
                    )

                # switch mapping to new cluster
                if current_cluster_mapping:
                    delete_cluster_judge_mapping(current_cluster_mapping.clusterid, judge.id)
                map_cluster_to_judge({"judgeid": judge.id, "clusterid": new_cluster})
                clusterid = new_cluster

                # create fresh sheets in new cluster using NEW flags
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

                # update booleans to new values
                judge.presentation = new_presentation
                judge.mdo = new_mdo
                judge.journal = new_journal
                judge.runpenalties = new_runpenalties
                judge.otherpenalties = new_otherpenalties
                if hasattr(judge, "redesign"):
                    judge.redesign = new_redesign
                if hasattr(judge, "championship"):
                    judge.championship = new_championship

            else:
                # Same cluster: selectively add/remove sheets per flag
                clusterid = current_cluster_id or new_cluster

                # presentation
                if new_presentation != judge.presentation and new_presentation is False:
                    delete_sheets_for_teams_in_cluster(judge.id, clusterid, True, False, False, False, False, False, False)
                    judge.presentation = False
                elif new_presentation != judge.presentation and new_presentation is True:
                    create_sheets_for_teams_in_cluster(judge.id, clusterid, True, False, False, False, False, False, False)
                    judge.presentation = True

                # journal
                if new_journal != judge.journal and new_journal is False:
                    delete_sheets_for_teams_in_cluster(judge.id, clusterid, False, True, False, False, False, False, False)
                    judge.journal = False
                elif new_journal != judge.journal and new_journal is True:
                    create_sheets_for_teams_in_cluster(judge.id, clusterid, False, True, False, False, False, False, False)
                    judge.journal = True

                # mdo
                if new_mdo != judge.mdo and new_mdo is False:
                    delete_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, True, False, False, False, False)
                    judge.mdo = False
                elif new_mdo != judge.mdo and new_mdo is True:
                    create_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, True, False, False, False, False)
                    judge.mdo = True

                # run penalties
                if new_runpenalties != judge.runpenalties and new_runpenalties is False:
                    delete_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, True, False, False, False)
                    judge.runpenalties = False
                elif new_runpenalties != judge.runpenalties and new_runpenalties is True:
                    create_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, True, False, False, False)
                    judge.runpenalties = True

                # other penalties
                if new_otherpenalties != judge.otherpenalties and new_otherpenalties is False:
                    delete_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, False, True, False, False)
                    judge.otherpenalties = False
                elif new_otherpenalties != judge.otherpenalties and new_otherpenalties is True:
                    create_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, False, True, False, False)
                    judge.otherpenalties = True

                # redesign
                if hasattr(judge, "redesign"):
                    if new_redesign != judge.redesign and new_redesign is False:
                        delete_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, False, False, True, False)
                        judge.redesign = False
                    elif new_redesign != judge.redesign and new_redesign is True:
                        create_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, False, False, True, False)
                        judge.redesign = True

                # championship
                if hasattr(judge, "championship"):
                    if new_championship != judge.championship and new_championship is False:
                        delete_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, False, False, False, True)
                        judge.championship = False
                    elif new_championship != judge.championship and new_championship is True:
                        create_sheets_for_teams_in_cluster(judge.id, clusterid, False, False, False, False, False, False, True)
                        judge.championship = True

                # keep mapping intact but ensure it exists
                if not MapJudgeToCluster.objects.filter(judgeid=judge.id, clusterid=clusterid).exists():
                    map_cluster_to_judge({"judgeid": judge.id, "clusterid": clusterid})

                # -------------------- ADDED: if sheets are simply missing, create them --------------------
                if missing_scoresheets:  # ADDED
                    create_sheets_for_teams_in_cluster(                   # ADDED
                        judge.id,                                        # ADDED
                        clusterid,                                       # ADDED
                        new_presentation, new_journal, new_mdo,          # ADDED
                        new_runpenalties, new_otherpenalties,            # ADDED
                        new_redesign, new_championship,                  # ADDED
                    )                                                    # ADDED
                # -----------------------------------------------------------------------------------------

            # -------------------- ADDED: ensure contest↔judge mapping exists --------------------
            try:  # ADDED
                if not MapContestToJudge.objects.filter(judgeid=judge.id, contestid=judge.contestid).exists():  # ADDED
                    create_contest_to_judge_map({ "contestid": judge.contestid, "judgeid": judge.id })          # ADDED
            except Exception:
                pass
            # ------------------------------------------------------------------------------------

            judge.save()

        serializer = JudgeSerializer(instance=judge)

    except Exception as e:
        raise ValidationError({"detail": str(e)})

    return Response({"judge": serializer.data, "clusterid": clusterid, "user": user_serializer.data}, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_judge(request, judge_id):
    try:
        judge = get_object_or_404(Judge, id=judge_id)
        scoresheet_mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id)
        scoresheet_ids = scoresheet_mappings.values_list('scoresheetid', flat=True)
        scoresheets = Scoresheet.objects.filter(id__in=scoresheet_ids)
        user_mapping = MapUserToRole.objects.get(role=3, relatedid=judge_id)
        user = get_object_or_404(User, id=user_mapping.uuid)
        cluster_mapping = MapJudgeToCluster.objects.get(judgeid=judge_id)
        teams_mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id)
        contest_mapping = MapContestToJudge.objects.filter(judgeid=judge_id)

        # delete associated user
        user.delete()
        user_mapping.delete()

        # delete associated scoresheets
        for scoresheet in scoresheets:
            scoresheet.delete()

        # delete associated judge-teams mappings
        for mapping in teams_mappings:
            mapping.delete()

        # delete associated judge-contest mapping
        contest_mapping.delete()

        # delete associated judge-cluster mapping
        cluster_mapping.delete()

        # delete the judge
        judge.delete()

        return Response({"detail": "Judge deleted successfully."}, status=status.HTTP_200_OK)

    except ValidationError as e:  # Catching ValidationErrors specifically
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def create_judge_instance(judge_data):
    serializer = JudgeSerializer(data=judge_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data
    raise ValidationError(serializer.errors)


def create_user_and_judge(data):
    # IMPORTANT: Judges use ONLY the shared judge password (role=3)
    user_data = {"username": data["username"], "password": data["password"]}
    user_response = create_user(user_data, send_email=False, enforce_unusable_password=True)
    if not user_response.get('user'):
        raise ValidationError('User creation failed.')

    # (Email intentionally NOT sent for judges)

    judge_data = {
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "phone_number": data["phone_number"],
        "contestid": data["contestid"],
        "presentation": data["presentation"],
        "mdo": data["mdo"],
        "journal": data["journal"],
        "runpenalties": data["runpenalties"],
        "otherpenalties": data["otherpenalties"],
        # new optional flags
        "redesign": data.get("redesign", False),
        "championship": data.get("championship", False),
        "role": data["role"]
    }
    judge_response = create_judge_instance(judge_data)
    if not judge_response.get('id'):
        raise ValidationError('Judge creation failed.')
    return user_response, judge_response


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def are_all_score_sheets_submitted(request):
    """
    Check if all score sheets assigned to a list of judges are submitted.
    Expects a JSON body with a list of judge objects.
    Optional query param: ?cluster_id=<id> to restrict to that cluster's teams.
    """
    judges = request.data

    if not judges:
        return Response({"detail": "No judges provided."}, status=status.HTTP_400_BAD_REQUEST)

    results = {}

    # Optional filter by cluster
    cluster_id = request.query_params.get('cluster_id')
    team_ids = None
    if cluster_id:
        from ..models import MapClusterToTeam
        team_ids = list(MapClusterToTeam.objects.filter(clusterid=cluster_id).values_list('teamid', flat=True))

    for judge in judges:
        judge_id = judge.get('id')

        if team_ids is not None:
            mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id, teamid__in=team_ids)
        else:
            mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id)

        if not mappings.exists():
            results[judge_id] = False
            continue

        required_sheet_ids = [m.scoresheetid for m in mappings]
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
@authentication_classes([SessionAuthentication])
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
