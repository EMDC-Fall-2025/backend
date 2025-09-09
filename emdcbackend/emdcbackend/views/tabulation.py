# emdcbackend/emdcbackend/views/tabulation.py
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

# ---------- helpers ----------

def qdiv(numer, denom):
    """
    Quiet division: returns 0.0 if denom is falsy/zero.
    Keeps your tabulation running even when no submissions exist for a category.
    """
    try:
        return float(numer) / float(denom) if denom else 0.0
    except Exception:
        return 0.0


# reference for this file's functions will be in a markdown file titled
# *Scoring Tabultaion Outline* in the onedrive

@api_view(["PUT"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def tabulate_scores(request):
    contest_id = request.data.get("contestid")
    if not contest_id:
        return Response({"detail": "contestid is required"}, status=status.HTTP_400_BAD_REQUEST)

    # --- collect Teams in the contest ---
    contest_team_ids = MapContestToTeam.objects.filter(contestid=contest_id)

    contestteams = []
    for mapping in contest_team_ids:
        try:
            tempteam = Teams.objects.get(id=mapping.teamid)
        except Teams.DoesNotExist:
            return Response({"detail": f"Team {mapping.teamid} not found"}, status=status.HTTP_404_NOT_FOUND)
        contestteams.append(tempteam)

    # --- collect Clusters in the contest (used later for ranks) ---
    contest_cluster_ids = MapContestToCluster.objects.filter(contestid=contest_id)
    clusters = []
    for mapping in contest_cluster_ids:
        try:
            tempcluster = JudgeClusters.objects.get(id=mapping.clusterid)
        except JudgeClusters.DoesNotExist:
            return Response({"detail": f"Cluster {mapping.clusterid} not found"}, status=status.HTTP_404_NOT_FOUND)
        clusters.append(tempcluster)

    # --- tabulate per team ---
    for team in contestteams:
        # get the team's scoresheets
        score_sheet_ids = MapScoresheetToTeamJudge.objects.filter(teamid=team.id)
        scoresheets = []
        for mapping in score_sheet_ids:
            try:
                tempscoresheet = Scoresheet.objects.get(id=mapping.scoresheetid)
            except Scoresheet.DoesNotExist:
                return Response(
                    {"detail": f"ScoreSheet {mapping.scoresheetid} not found from mapping"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            scoresheets.append(tempscoresheet)

        # totalscores indices (sums & counters):
        # 0: presentation sum, 1: presentation count
        # 2: journal sum,      3: journal count
        # 4: machine sum,      5: machine count
        # 6: general penalties (sum; NOT averaged)
        # 7: run1 penalties sum, 8: run1 count
        # 9: run2 penalties sum, 10: run2 count
        totalscores = [0] * 11

        for sheet in scoresheets:
            if not sheet.isSubmitted:
                continue

            if sheet.sheetType == ScoresheetEnum.PRESENTATION:
                totalscores[0] += (
                    sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                    sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8
                )
                totalscores[1] += 1

            elif sheet.sheetType == ScoresheetEnum.JOURNAL:
                totalscores[2] += (
                    sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                    sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8
                )
                totalscores[3] += 1

            elif sheet.sheetType == ScoresheetEnum.MACHINEDESIGN:
                totalscores[4] += (
                    sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                    sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8
                )
                totalscores[5] += 1

            elif sheet.sheetType == ScoresheetEnum.RUNPENALTIES:
                # NOTE: fixed wrong indices. We add into 7 and 9 (not 8/10)
                totalscores[7] += (
                    sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                    sheet.field5 + sheet.field6 + sheet.field7 + sheet.field8
                )
                totalscores[8] += 1  # count for run 1

                totalscores[9] += (
                    sheet.field10 + sheet.field11 + sheet.field12 + sheet.field13 +
                    sheet.field14 + sheet.field15 + sheet.field16 + sheet.field17
                )
                totalscores[10] += 1  # count for run 2

            elif sheet.sheetType == ScoresheetEnum.OTHERPENALTIES:
                # NOTE: fixed to accumulate (+=) instead of overwrite (= +…)
                totalscores[6] += (
                    sheet.field1 + sheet.field2 + sheet.field3 + sheet.field4 +
                    sheet.field5 + sheet.field6 + sheet.field7
                )

        # --- compute averages safely (0 if no submissions) ---
        team.presentation_score   = qdiv(totalscores[0], totalscores[1])
        team.journal_score        = qdiv(totalscores[2], totalscores[3])
        team.machinedesign_score  = qdiv(totalscores[4], totalscores[5])

        run1_avg = qdiv(totalscores[7], totalscores[8])
        run2_avg = qdiv(totalscores[9], totalscores[10])

        team.penalties_score = totalscores[6] + run1_avg + run2_avg
        team.total_score = (team.presentation_score + team.journal_score + team.machinedesign_score) - team.penalties_score
        team.save()

    # --- set ranks (cluster & contest) ---
    for cluster in clusters:
        set_cluster_rank({"clusterid": cluster.id})
    set_team_rank({"contestid": contest_id})

    return Response(status=status.HTTP_200_OK)


# this function iterates through each team in the contest and sets the rank of the team based on the total score.
def set_team_rank(data):
    contest_team_ids = MapContestToTeam.objects.filter(contestid=data["contestid"])
    contestteams = []
    for mapping in contest_team_ids:
        try:
            tempteam = Teams.objects.get(id=mapping.teamid)
        except Teams.DoesNotExist:
            raise ValidationError("Team Cannot Be Found.")
        if not tempteam.organizer_disqualified:
            contestteams.append(tempteam)

    # sort by total score descending and assign ranks
    contestteams.sort(key=lambda x: x.total_score, reverse=True)
    for x in range(len(contestteams)):
        contestteams[x].team_rank = x + 1
        contestteams[x].save()
    return


# function to set the rank of the teams in a cluster
def set_cluster_rank(data):
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


# function to get all scoresheets that a team has submitted
@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_scoresheet_comments_by_team_id(request):
    # For GET, better to use query_params, but leaving your contract intact.
    scoresheeids = MapScoresheetToTeamJudge.objects.filter(teamid=request.data.get("teamid"))
    scoresheets = Scoresheet.objects.filter(id__in=scoresheeids)
    comments = []
    for sheet in scoresheets:
        if sheet.field9 != "":
            comments.append(sheet.field9)
    return Response({"Comments": comments}, status=status.HTTP_200_OK)
