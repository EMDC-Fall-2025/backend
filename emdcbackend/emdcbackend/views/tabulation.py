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
