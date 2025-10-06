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
    # Implemented as (-score, id) ascending to avoid reverse=True complexity
    def _score(t):
        v = getattr(t, score_attr)
        return float(v) if v is not None else 0.0
    return sorted(teams, key=lambda t: (-_score(t), t.id))


def _compute_totals_for_team(team: Teams):
    """
    Compute totals/averages exactly like your tabulate_scores loop.
    Mutates and saves the team with updated scores.
    """
    score_map = MapScoresheetToTeamJudge.objects.filter(teamid=team.id)
    totalscores = [0] * 11  # 0..10 as documented

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


# ---------- existing endpoints ----------

@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def tabulate_scores(request):
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"detail": "contestid is required"}, status=status.HTTP_400_BAD_REQUEST)

    # collect teams
    contest_team_ids = MapContestToTeam.objects.filter(contestid=contest_id)
    contestteams = []
    for mapping in contest_team_ids:
        try:
            tempteam = Teams.objects.get(id=mapping.teamid)
        except Teams.DoesNotExist:
            return Response({"detail": f"Team {mapping.teamid} not found"}, status=status.HTTP_404_NOT_FOUND)
        contestteams.append(tempteam)

    # collect clusters (for later ranking)
    contest_cluster_ids = MapContestToCluster.objects.filter(contestid=contest_id)
    clusters = []
    for mapping in contest_cluster_ids:
        try:
            tempcluster = JudgeClusters.objects.get(id=mapping.clusterid)
        except JudgeClusters.DoesNotExist:
            return Response({"detail": f"Cluster {mapping.clusterid} not found"}, status=status.HTTP_404_NOT_FOUND)
        clusters.append(tempcluster)

    # tabulate per team
    for team in contestteams:
        _compute_totals_for_team(team)

    # set ranks
    for cluster in clusters:
        set_cluster_rank({"clusterid": cluster.id})
    set_team_rank({"contestid": contest_id})

    return Response(status=status.HTTP_200_OK)


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


@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_scoresheet_comments_by_team_id(request):
    scoresheeids = MapScoresheetToTeamJudge.objects.filter(teamid=request.data.get("teamid"))
    scoresheets = Scoresheet.objects.filter(id__in=scoresheeids)
    comments = []
    for sheet in scoresheets:
        if sheet.field9 != "":
            comments.append(sheet.field9)
    return Response({"Comments": comments}, status=status.HTTP_200_OK)


# ---------- NEW: phase endpoints ----------

@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def preliminary_results(request):
    """
    Advance EXACTLY X teams per cluster by total_score.
    Body: { "contestid": <int>, "advance_count": <int> }
    """
    contest_id = request.data.get("contestid")
    advance_count = request.data.get("advance_count")
    if not contest_id:
        return Response({"ok": False, "message": "contestid is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        x = int(advance_count)
        if x <= 0:
            raise ValueError
    except Exception:
        return Response({"ok": False, "message": "advance_count must be a positive integer."}, status=status.HTTP_400_BAD_REQUEST)

    # make totals fresh
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

        # mark top X as advanced; if fewer than X teams, advance all
        top = ordered[:x] if x < len(ordered) else ordered[:]
        top_ids = {t.id for t in top}

        for t in ordered:
            t.advanced_to_championship = (t.id in top_ids)
            t.save(update_fields=["advanced_to_championship"])

        response_clusters.append({
            "cluster_id": cm.clusterid,
            "teams": [
                {
                    "team_id": t.id,
                    "total": float(t.total_score or 0.0),
                    "cluster_rank": int(t.cluster_rank) if t.cluster_rank else None,
                    "advanced": bool(t.advanced_to_championship),
                }
                for t in ordered
            ]
        })

    return Response({"ok": True, "message": "Preliminary complete.", "data": response_clusters}, status=status.HTTP_200_OK)


@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def championship_results(request):
    """
    Championship pool = advanced teams. Rank by journal_score only.
    Body: { "contestid": <int> }
    """
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"ok": False, "message": "contestid is required."}, status=status.HTTP_400_BAD_REQUEST)

    recompute_totals_and_ranks(contest_id)

    # pool = all advanced teams in this contest
    team_ids = MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
    pool = list(Teams.objects.filter(id__in=list(team_ids), advanced_to_championship=True))

    ordered = sort_by_score_with_id_fallback(pool, "journal_score")

    for i, t in enumerate(ordered, start=1):
        t.championship_rank = i
        t.save(update_fields=["championship_rank"])

    payload = [
        {"team_id": t.id, "journal": float(t.journal_score or 0.0), "championship_rank": t.championship_rank}
        for t in ordered
    ]
    return Response({"ok": True, "message": "Championship ranking complete.", "data": payload}, status=status.HTTP_200_OK)


@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def redesign_results(request):
    """
    Redesign pool = NOT advanced teams. Rank by total_score (single pool).
    Body: { "contestid": <int> }
    """
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"ok": False, "message": "contestid is required."}, status=status.HTTP_400_BAD_REQUEST)

    recompute_totals_and_ranks(contest_id)

    team_ids = MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
    pool = list(Teams.objects.filter(id__in=list(team_ids), advanced_to_championship=False))

    ordered = sort_by_score_with_id_fallback(pool, "total_score")
    payload = [{"team_id": t.id, "total": float(t.total_score or 0.0)} for t in ordered]

    return Response({"ok": True, "message": "Redesign ranking prepared.", "data": payload}, status=status.HTTP_200_OK)
