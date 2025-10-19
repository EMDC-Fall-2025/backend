from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User

from ..models import (
    Teams,
    Scoresheet,
    MapScoresheetToTeamJudge,
    MapContestToTeam,
    ScoresheetEnum,
    MapClusterToTeam,
    JudgeClusters,
    MapContestToCluster,
    MapContestToOrganizer,
    MapUserToRole,
    MapJudgeToCluster,
    Judge,
)

# ---------- Shared Helpers ----------

def qdiv(numer, denom):
    """Quiet division: returns 0.0 if denom is falsy/zero."""
    try:
        return float(numer) / float(denom) if denom else 0.0
    except Exception:
        return 0.0


def sort_by_score_with_id_fallback(teams, score_attr: str):
    """Sort by score descending, then team.id ascending."""
    def _score(t):
        v = getattr(t, score_attr)
        return float(v) if v is not None else 0.0
    return sorted(teams, key=lambda t: (-_score(t), t.id))


def _compute_totals_for_team(team: Teams):
    """Compute totals and averages for a given team."""
    score_map = MapScoresheetToTeamJudge.objects.filter(teamid=team.id)
    totals = [0] * 11

    for mapping in score_map:
        try:
            sheet = Scoresheet.objects.get(id=mapping.scoresheetid)
        except Scoresheet.DoesNotExist:
            continue
        if not sheet.isSubmitted:
            continue

        if sheet.sheetType == ScoresheetEnum.PRESENTATION:
            totals[0] += sum(getattr(sheet, f"field{i}") for i in range(1, 9))
            totals[1] += 1
        elif sheet.sheetType == ScoresheetEnum.JOURNAL:
            totals[2] += sum(getattr(sheet, f"field{i}") for i in range(1, 9))
            totals[3] += 1
        elif sheet.sheetType == ScoresheetEnum.MACHINEDESIGN:
            totals[4] += sum(getattr(sheet, f"field{i}") for i in range(1, 9))
            totals[5] += 1
        elif sheet.sheetType == ScoresheetEnum.RUNPENALTIES:
            totals[7] += sum(getattr(sheet, f"field{i}") for i in range(1, 9))
            totals[8] += 1
            totals[9] += sum(getattr(sheet, f"field{i}") for i in range(10, 18))
            totals[10] += 1
        elif sheet.sheetType == ScoresheetEnum.OTHERPENALTIES:
            totals[6] += sum(getattr(sheet, f"field{i}") for i in range(1, 8))

    # compute averages and totals
    team.presentation_score = qdiv(totals[0], totals[1])
    team.journal_score = qdiv(totals[2], totals[3])
    team.machinedesign_score = qdiv(totals[4], totals[5])

    run1_avg = qdiv(totals[7], totals[8])
    run2_avg = qdiv(totals[9], totals[10])
    team.penalties_score = totals[6] + run1_avg + run2_avg
    team.total_score = (
        team.presentation_score + team.journal_score + team.machinedesign_score
    ) - team.penalties_score
    team.save()


def set_team_rank(data):
    """Set contest-wide rank by total_score for eligible teams."""
    contest_team_ids = MapContestToTeam.objects.filter(contestid=data["contestid"])
    contestteams = []
    for mapping in contest_team_ids:
        try:
            t = Teams.objects.get(id=mapping.teamid)
            if not t.organizer_disqualified:
                contestteams.append(t)
        except Teams.DoesNotExist:
            continue

    contestteams.sort(key=lambda x: x.total_score, reverse=True)
    for rank, team in enumerate(contestteams, start=1):
        team.team_rank = rank
        team.save()


def set_cluster_rank(data):
    """Set per-cluster rank by total_score for eligible teams."""
    cluster_team_ids = MapClusterToTeam.objects.filter(clusterid=data["clusterid"])
    clusterteams = []
    for mapping in cluster_team_ids:
        try:
            t = Teams.objects.get(id=mapping.teamid)
            if not t.organizer_disqualified:
                clusterteams.append(t)
        except Teams.DoesNotExist:
            continue

    clusterteams.sort(key=lambda x: x.total_score, reverse=True)
    for rank, team in enumerate(clusterteams, start=1):
        team.cluster_rank = rank
        team.save()


def _ensure_requester_is_organizer_of_contest(user, contest_id: int):
    """Allow only organizers mapped to this contest."""
    organizer_ids_for_user = list(
        MapUserToRole.objects.filter(
            uuid=user.id, role=MapUserToRole.RoleEnum.ORGANIZER
        ).values_list("relatedid", flat=True)
    )
    return MapContestToOrganizer.objects.filter(
        contestid=contest_id, organizerid__in=organizer_ids_for_user
    ).exists()


def recompute_totals_and_ranks(contest_id: int):
    """Recompute all teams' totals for a contest, then reapply cluster & contest ranks."""
    contest_team_ids = MapContestToTeam.objects.filter(contestid=contest_id)
    teams = []
    for m in contest_team_ids:
        try:
            teams.append(Teams.objects.get(id=m.teamid))
        except Teams.DoesNotExist:
            continue

    for t in teams:
        _compute_totals_for_team(t)

    for m in MapContestToCluster.objects.filter(contestid=contest_id):
        set_cluster_rank({"clusterid": m.clusterid})
    set_team_rank({"contestid": contest_id})


# ---------- Endpoints ----------

@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def tabulate_scores(request):
    """Recompute totals and ranks for all teams."""
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"detail": "contestid is required"}, status=400)

    recompute_totals_and_ranks(contest_id)
    return Response(status=200)

@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def preliminary_results(request):
    """
    NEW behavior: show ranked results per cluster, but DO NOT auto-advance anyone.
    Organizers will choose advancers using set_advancers().
    Body: { "contestid": <int> }
    """
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"ok": False, "message": "contestid is required."}, status=status.HTTP_400_BAD_REQUEST)

    # recompute + apply ranks
    recompute_totals_and_ranks(contest_id)

    response_clusters = []
    for cm in MapContestToCluster.objects.filter(contestid=contest_id):
        # teams in this cluster
        team_maps = MapClusterToTeam.objects.filter(clusterid=cm.clusterid)
        cluster_teams = []
        for m in team_maps:
            try:
                cluster_teams.append(Teams.objects.get(id=m.teamid))
            except Teams.DoesNotExist:
                continue

        ordered = sort_by_score_with_id_fallback(cluster_teams, "total_score")
        response_clusters.append({
            "cluster_id": cm.clusterid,
            "teams": [
                {
                    "team_id": t.id,
                    "team_name": t.team_name,
                    "total": float(t.total_score or 0.0),
                    "cluster_rank": int(t.cluster_rank) if t.cluster_rank else None,
                    "advanced": bool(t.advanced_to_championship),
                }
                for t in ordered
            ]
        })

    return Response({"ok": True, "message": "Preliminary standings computed.", "data": response_clusters}, status=status.HTTP_200_OK)


@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def set_advancers(request):
    """
    Organizers pick which teams advance to CHAMPIONSHIP (single pool later).
    Body: { "contestid": <int>, "team_ids": [1,2,3,...] }  (IDs that ADVANCE)
    Security: requester must be an organizer of this contest.
    Behavior:
      - All teams in the contest are set advanced_to_championship=False
      - Provided team_ids are set to True
      - Clears previous championship_rank (if any)
    """
    contest_id = request.data.get("contestid")
    team_ids = request.data.get("team_ids")

    if not contest_id:
        return Response({"ok": False, "message": "contestid is required"}, status=400)
    if not isinstance(team_ids, list):
        return Response({"ok": False, "message": "team_ids must be a list of ints"}, status=400)

    if not _ensure_requester_is_organizer_of_contest(request.user, contest_id):
        return Response({"ok": False, "message": "Organizer of this contest required."}, status=403)

    # Limit changes to teams actually in the contest
    contest_team_ids = list(
        MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
    )

    # reset everyone in contest
    Teams.objects.filter(id__in=contest_team_ids).update(advanced_to_championship=False, championship_rank=None)

    # set selected advancers (intersection safety)
    valid_selection = [tid for tid in team_ids if tid in contest_team_ids]
    Teams.objects.filter(id__in=valid_selection).update(advanced_to_championship=True)

    # Return summary
    advancers = list(
        Teams.objects.filter(id__in=contest_team_ids, advanced_to_championship=True)
            .values("id", "team_name")
            .order_by("id")
    )
    return Response({"ok": True, "advanced_count": len(advancers), "advanced": advancers}, status=200)


@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_advancers(request):
    """
    Convenience endpoint to list current advancers for a contest.
    Query: ?contestid=<int>
    """
    try:
        contest_id = int(request.GET.get("contestid"))
    except Exception:
        return Response({"ok": False, "message": "contestid is required as query param"}, status=400)

    contest_team_ids = list(
        MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
    )
    advancers = list(
        Teams.objects.filter(id__in=contest_team_ids, advanced_to_championship=True)
            .values("id", "team_name")
            .order_by("id")
    )
    return Response({"ok": True, "advanced_count": len(advancers), "advanced": advancers}, status=200)


@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def championship_results(request):
    """
    Championship pool = teams flagged as advanced_to_championship=True (single pool).
    Rank by journal_score only.
    Body: { "contestid": <int> }
    """
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"ok": False, "message": "contestid is required."}, status=status.HTTP_400_BAD_REQUEST)

    # keep computed fields fresh (in case penalties/fields changed)
    recompute_totals_and_ranks(contest_id)

    team_ids = MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
    pool = list(Teams.objects.filter(id__in=list(team_ids), advanced_to_championship=True))

    ordered = sort_by_score_with_id_fallback(pool, "journal_score")

    for i, t in enumerate(ordered, start=1):
        t.championship_rank = i
        t.save(update_fields=["championship_rank"])

    payload = [
        {"team_id": t.id, "team_name": t.team_name, "journal": float(t.journal_score or 0.0), "championship_rank": t.championship_rank}
        for t in ordered
    ]
    return Response({"ok": True, "message": "Championship ranking complete.", "data": payload}, status=status.HTTP_200_OK)


@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def redesign_results(request):
    """
    Redesign pool = teams with advanced_to_championship=False in this contest (single pool).
    Rank by total_score.
    Body: { "contestid": <int> }
    """
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"ok": False, "message": "contestid is required."}, status=status.HTTP_400_BAD_REQUEST)

    recompute_totals_and_ranks(contest_id)

    team_ids = MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
    pool = list(Teams.objects.filter(id__in=list(team_ids), advanced_to_championship=False))

    ordered = sort_by_score_with_id_fallback(pool, "total_score")
    payload = [{"team_id": t.id, "team_name": t.team_name, "total": float(t.total_score or 0.0)} for t in ordered]

    return Response({"ok": True, "message": "Redesign ranking prepared.", "data": payload}, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def advance_to_championship(request):
    contest_id = request.data.get("contestid")
    championship_team_ids = request.data.get("championship_team_ids", [])

    if not contest_id:
        return Response({"ok": False, "message": "contestid is required"}, status=400)
    if not isinstance(championship_team_ids, list):
        return Response({"ok": False, "message": "championship_team_ids must be a list"}, status=400)

    # Security check
    if not _ensure_requester_is_organizer_of_contest(request.user, contest_id):
        return Response({"ok": False, "message": "Organizer of this contest required."}, status=403)

    try:
        contest_team_ids = list(
            MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
        )
        
        Teams.objects.filter(id__in=contest_team_ids).update(
            advanced_to_championship=False, 
            championship_rank=None
        )
        
        valid_championship_teams = [tid for tid in championship_team_ids if tid in contest_team_ids]
        
        if valid_championship_teams:
            Teams.objects.filter(id__in=valid_championship_teams).update(advanced_to_championship=True)
        
        non_championship_teams = [tid for tid in contest_team_ids if tid not in valid_championship_teams]
        
        contest_clusters = MapContestToCluster.objects.filter(contestid=contest_id)
        championship_cluster = None
        redesign_cluster = None
        
        for cc in contest_clusters:
            try:
                cluster = JudgeClusters.objects.get(id=cc.clusterid)
                
                if cluster.cluster_type == 'championship':
                    championship_cluster = cluster
                elif cluster.cluster_type == 'redesign':
                    redesign_cluster = cluster
                elif 'championship' in cluster.cluster_name.lower() and not championship_cluster:
                    championship_cluster = cluster
                elif 'redesign' in cluster.cluster_name.lower() and not redesign_cluster:
                    redesign_cluster = cluster
            except JudgeClusters.DoesNotExist:
                continue
        
        if not championship_cluster:
            return Response({"ok": False, "message": "Championship cluster not found. Please create it first."}, status=400)
        if not redesign_cluster:
            return Response({"ok": False, "message": "Redesign cluster not found. Please create it first."}, status=400)
        
        championship_cluster.is_active = True
        championship_cluster.save()
            
        redesign_cluster.is_active = True
        redesign_cluster.save()
        
        MapClusterToTeam.objects.filter(clusterid=championship_cluster.id).delete()
        MapClusterToTeam.objects.filter(clusterid=redesign_cluster.id).delete()
        
        championship_teams_data = []
        redesign_teams_data = []
        for team_id in valid_championship_teams:
            try:
                team = Teams.objects.get(id=team_id)
                # Reset scores for championship round (except journal score)
                team.presentation_score = 0.0
                team.machinedesign_score = 0.0
                team.penalties_score = 0.0
                team.redesign_score = 0.0
                team.championship_score = 0.0
                # Keep journal_score from preliminary round
                # Let tabulation system calculate total_score properly
                team.save()
                
                championship_teams_data.append(team)
                MapClusterToTeam.objects.create(clusterid=championship_cluster.id, teamid=team.id)
            except Teams.DoesNotExist:
                continue
        
        for team_id in non_championship_teams:
            try:
                team = Teams.objects.get(id=team_id)
                team.presentation_score = 0.0
                team.machinedesign_score = 0.0
                team.penalties_score = 0.0
                team.redesign_score = 0.0
                team.championship_score = 0.0
                team.save()
                
                redesign_teams_data.append(team)
                MapClusterToTeam.objects.create(clusterid=redesign_cluster.id, teamid=team.id)
            except Teams.DoesNotExist:
                continue
        
        # 6. Update judge flags for championship/redesign clusters
        from ..models import MapJudgeToCluster, Judge
        
        # Update judges in championship cluster to have championship=True
        championship_judge_mappings = MapJudgeToCluster.objects.filter(clusterid=championship_cluster.id)
        
        for mapping in championship_judge_mappings:
            try:
                judge = Judge.objects.get(id=mapping.judgeid)
                if not judge.championship:
                    judge.championship = True
                    judge.save()
            except Judge.DoesNotExist:
                continue
        
        redesign_judge_mappings = MapJudgeToCluster.objects.filter(clusterid=redesign_cluster.id)
        
        for mapping in redesign_judge_mappings:
            try:
                judge = Judge.objects.get(id=mapping.judgeid)
                if not judge.redesign:
                    judge.redesign = True
                    judge.save()
            except Judge.DoesNotExist:
                continue
        
        # 7. Clear existing championship/redesign scoresheets to avoid duplicates
        from ..models import MapScoresheetToTeamJudge, Scoresheet
        
        championship_judge_ids = [mapping.judgeid for mapping in championship_judge_mappings]
        if championship_judge_ids:
            MapScoresheetToTeamJudge.objects.filter(
                judgeid__in=championship_judge_ids,
                sheetType__in=[6, 7]
            ).delete()
        
        redesign_judge_ids = [mapping.judgeid for mapping in redesign_judge_mappings]
        if redesign_judge_ids:
            MapScoresheetToTeamJudge.objects.filter(
                judgeid__in=redesign_judge_ids,
                sheetType__in=[6, 7]
            ).delete()
        
        from .scoresheets import create_scoresheets_for_judges_in_cluster
        
        create_scoresheets_for_judges_in_cluster(championship_cluster.id)
        create_scoresheets_for_judges_in_cluster(redesign_cluster.id)
        
        # Recompute totals and ranks for the new clusters
        recompute_totals_and_ranks(contest_id)
        
        return Response({
            "ok": True,
            "message": "Championship advancement completed successfully",
            "data": {
                "championship_cluster_id": championship_cluster.id,
                "redesign_cluster_id": redesign_cluster.id,
                "championship_teams_count": len(championship_teams_data),
                "redesign_teams_count": len(redesign_teams_data)
            }
        }, status=200)
        
    except Exception as e:
        return Response({"ok": False, "message": f"Error during championship advancement: {str(e)}"}, status=500)


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def undo_championship_advancement(request):
    """
    Undo championship advancement and revert to preliminary state:
    1. Deactivate championship and redesign clusters
    2. Remove teams from championship/redesign clusters
    3. Reset team scores and flags
    4. Move teams back to original preliminary clusters
    
    Body: { 
        "contestid": <int>
    }
    """
    contest_id = request.data.get("contestid")

    if not contest_id:
        return Response({"ok": False, "message": "contestid is required"}, status=400)

    # Security check
    if not _ensure_requester_is_organizer_of_contest(request.user, contest_id):
        return Response({"ok": False, "message": "Organizer of this contest required."}, status=403)

    try:
        # 1. Get all teams in contest
        contest_team_ids = list(
            MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
        )
        
        # 2. Find championship and redesign clusters
        contest_clusters = MapContestToCluster.objects.filter(contestid=contest_id)
        championship_cluster = None
        redesign_cluster = None
        
        for cc in contest_clusters:
            try:
                cluster = JudgeClusters.objects.get(id=cc.clusterid)
                # Use cluster_type field for robust detection
                if cluster.cluster_type == 'championship':
                    championship_cluster = cluster
                elif cluster.cluster_type == 'redesign':
                    redesign_cluster = cluster
                # Fallback: check by name for existing clusters (transition period)
                elif 'championship' in cluster.cluster_name.lower() and not championship_cluster:
                    championship_cluster = cluster
                elif 'redesign' in cluster.cluster_name.lower() and not redesign_cluster:
                    redesign_cluster = cluster
            except JudgeClusters.DoesNotExist:
                continue
        
        # 3. Deactivate clusters
        if championship_cluster:
            championship_cluster.is_active = False
            championship_cluster.save()
            
        if redesign_cluster:
            redesign_cluster.is_active = False
            redesign_cluster.save()
        
        # 4. Remove teams from championship/redesign clusters
        if championship_cluster:
            MapClusterToTeam.objects.filter(clusterid=championship_cluster.id).delete()
            
        if redesign_cluster:
            MapClusterToTeam.objects.filter(clusterid=redesign_cluster.id).delete()
        
        # 4.5. Delete championship/redesign scoresheets
        if championship_cluster:
            # Get all judges in championship cluster
            championship_judges = MapJudgeToCluster.objects.filter(clusterid=championship_cluster.id)
            for judge_mapping in championship_judges:
                # Delete championship scoresheets (type 7) for this judge
                championship_scoresheets = MapScoresheetToTeamJudge.objects.filter(
                    judgeid=judge_mapping.judgeid,
                    sheetType=7  # championship
                )
                championship_scoresheets.delete()
        
        if redesign_cluster:
            # Get all judges in redesign cluster
            redesign_judges = MapJudgeToCluster.objects.filter(clusterid=redesign_cluster.id)
            for judge_mapping in redesign_judges:
                # Delete redesign scoresheets (type 6) for this judge
                redesign_scoresheets = MapScoresheetToTeamJudge.objects.filter(
                    judgeid=judge_mapping.judgeid,
                    sheetType=6  # redesign
                )
                redesign_scoresheets.delete()
        
        # 5. Reset team flags and scores
        Teams.objects.filter(id__in=contest_team_ids).update(
            advanced_to_championship=False,
            championship_rank=None,
            presentation_score=0.0,
            machinedesign_score=0.0,
            penalties_score=0.0,
            redesign_score=0.0,
            championship_score=0.0,
            total_score=0.0
        )
        
        # 6. Move teams back to original preliminary clusters (if any exist)
        preliminary_clusters = []
        for cc in contest_clusters:
            try:
                cluster = JudgeClusters.objects.get(id=cc.clusterid)
                cluster_type = getattr(cluster, 'cluster_type', None)
                if cluster_type == 'preliminary' or cluster_type is None or cluster_type == 'NO_TYPE_FIELD':
                    preliminary_clusters.append(cluster)
            except JudgeClusters.DoesNotExist:
                continue
        
        if preliminary_clusters:
            # Assign teams to the first preliminary cluster found
            main_cluster = preliminary_clusters[0]
            for team_id in contest_team_ids:
                MapClusterToTeam.objects.create(clusterid=main_cluster.id, teamid=team_id)
        
        # 7. Recompute totals and ranks
        recompute_totals_and_ranks(contest_id)
        
        return Response({
            "ok": True,
            "message": "Championship advancement undone successfully",
            "data": {
                "teams_reset": len(contest_team_ids),
                "championship_cluster_deactivated": championship_cluster is not None,
                "redesign_cluster_deactivated": redesign_cluster is not None
            }
        }, status=200)
        
    except Exception as e:
        return Response({"ok": False, "message": f"Error undoing championship advancement: {str(e)}"}, status=500)