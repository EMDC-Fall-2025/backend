from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

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

# ---------- shared helpers ----------

def qdiv(numer, denom):
    """Quiet division: returns 0.0 if denom is falsy/zero."""
    try:
        return float(numer) / float(denom) if denom else 0.0
    except Exception:
        return 0.0


def sort_by_score_with_id_fallback(teams, score_attr: str):
    """
    Deterministic sort:
    - primary: score descending (higher first)
    - tie-break: team.id ascending (lower id first)
    """
    def _score(t):
        v = getattr(t, score_attr)
        return float(v) if v is not None else 0.0
    return sorted(teams, key=lambda t: (-_score(t), t.id))


def _compute_totals_for_team(team: Teams):
    """
    Compute totals/averages exactly like your original tabulate loop.
    Mutates and saves the team with updated scores.
    """
    score_map = MapScoresheetToTeamJudge.objects.filter(teamid=team.id)
    totalscores = [0] * 11  # indices documented below

    for mapping in score_map:
        try:
            sheet = Scoresheet.objects.get(id=mapping.scoresheetid)
        except Scoresheet.DoesNotExist:
            continue
        if not sheet.isSubmitted:
            continue

        if sheet.sheetType == ScoresheetEnum.PRESENTATION:
            totalscores[0] += (sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                               sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8)
            totalscores[1] += 1
        elif sheet.sheetType == ScoresheetEnum.JOURNAL:
            totalscores[2] += (sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                               sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8)
            totalscores[3] += 1
        elif sheet.sheetType == ScoresheetEnum.MACHINEDESIGN:
            totalscores[4] += (sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                               sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8)
            totalscores[5] += 1
        elif sheet.sheetType == ScoresheetEnum.RUNPENALTIES:
            totalscores[7] += (sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                               sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8)
            totalscores[8] += 1
            totalscores[9] += (sheet.field10 + sheet.field11 + sheet.field12 + sheet.field13 +
                               sheet.field14 + sheet.field15 + sheet.field16 + sheet.field17)
            totalscores[10] += 1
        elif sheet.sheetType == ScoresheetEnum.OTHERPENALTIES:
            totalscores[6] += (sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                               sheet.field5 + sheet.field6 + sheet.field7)

    team.presentation_score   = qdiv(totalscores[0], totalscores[1])
    team.journal_score        = qdiv(totalscores[2], totalscores[3])
    team.machinedesign_score  = qdiv(totalscores[4], totalscores[5])

    run1_avg = qdiv(totalscores[7], totalscores[8])
    run2_avg = qdiv(totalscores[9], totalscores[10])

    team.penalties_score = totalscores[6] + run1_avg + run2_avg
    team.total_score = (team.presentation_score + team.journal_score + team.machinedesign_score) - team.penalties_score
    team.save()


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


# ---------- ranking primitives ----------

def set_team_rank(data):
    """Set contest-wide rank by total_score for eligible (non-organizer-disqualified) teams."""
    contest_team_ids = MapContestToTeam.objects.filter(contestid=data["contestid"])
    contestteams = []
    for mapping in contest_team_ids:
        try:
            tempteam = Teams.objects.get(id=mapping.teamid)
        except Teams.DoesNotExist:
            raise ValidationError("Team Cannot Be Found.")
        if not tempteam.organizer_disqualified:
            contestteams.append(tempteam)

    contestteams.sort(key=lambda x: x.total_score, reverse=True)
    for x in range(len(contestteams)):
        contestteams[x].team_rank = x + 1
        contestteams[x].save()
    return


def set_cluster_rank(data):
    """Set per-cluster rank by total_score for eligible teams."""
    cluster_team_ids = MapClusterToTeam.objects.filter(clusterid=data["clusterid"])
    clusterteams = []
    for mapping in cluster_team_ids:
        try:
            tempteam = Teams.objects.get(id=mapping.teamid)
        except Teams.DoesNotExist:
            raise ValidationError("Team Cannot Be Found.")
        if not tempteam.organizer_disqualified:
            clusterteams.append(tempteam)

    clusterteams.sort(key=lambda x: x.total_score, reverse=True)
    for x in range(len(clusterteams)):
        clusterteams[x].cluster_rank = x + 1
        clusterteams[x].save()
    return


def _ensure_requester_is_organizer_of_contest(user, contest_id: int):
    """
    Allow only organizers mapped to this contest.
    """
    organizer_ids_for_user = list(
        MapUserToRole.objects.filter(
            uuid=user.id, role=MapUserToRole.RoleEnum.ORGANIZER
        ).values_list("relatedid", flat=True)
    )
    return MapContestToOrganizer.objects.filter(
        contestid=contest_id, organizerid__in=organizer_ids_for_user
    ).exists()


# ---------- endpoints ----------

@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def tabulate_scores(request):
    """
    Recompute totals and set cluster+contest ranks. Does NOT change advancement flags.
    Body: { "contestid": <int> }
    """
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"detail": "contestid is required"}, status=status.HTTP_400_BAD_REQUEST)

    # recompute + ranks
    recompute_totals_and_ranks(contest_id)
    return Response(status=status.HTTP_200_OK)


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
