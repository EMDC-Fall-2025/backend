from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from ..models import (
    Teams,
    MapContestToTeam,
    MapClusterToTeam,
    JudgeClusters,
    MapContestToCluster,
    MapContestToOrganizer,
    MapUserToRole,
    MapJudgeToCluster,
    Judge,
    MapScoresheetToTeamJudge,
)
from .tabulation import recompute_totals_and_ranks, _ensure_requester_is_organizer_of_contest


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
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
                # Store preliminary results before advancing
                team.preliminary_presentation_score = team.presentation_score
                team.preliminary_journal_score = team.journal_score
                team.preliminary_machinedesign_score = team.machinedesign_score
                team.preliminary_penalties_score = team.penalties_score
                team.preliminary_total_score = team.total_score
                
                # Championship round: only need journal from preliminary + championship score
                team.championship_score = 0.0
                team.total_score = 0.0  # Will be calculated by championship tabulation
                
                team.save()
                
                championship_teams_data.append(team)
                MapClusterToTeam.objects.create(clusterid=championship_cluster.id, teamid=team.id)
            except Teams.DoesNotExist:
                continue
        
        for team_id in non_championship_teams:
            try:
                team = Teams.objects.get(id=team_id)
                # Store preliminary results before advancing
                team.preliminary_presentation_score = team.presentation_score
                team.preliminary_journal_score = team.journal_score
                team.preliminary_machinedesign_score = team.machinedesign_score
                team.preliminary_penalties_score = team.penalties_score
                team.preliminary_total_score = team.total_score
                
                # Redesign round: only need redesign score (all categories in one scoresheet)
                
                team.redesign_score = 0.0
                team.total_score = 0.0  # Will be calculated by redesign tabulation
                
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
@authentication_classes([SessionAuthentication])
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
        
        # 5. Restore preliminary scores and reset team flags
        for team_id in contest_team_ids:
            try:
                team = Teams.objects.get(id=team_id)
                # Restore preliminary scores
                team.presentation_score = team.preliminary_presentation_score
                team.journal_score = team.preliminary_journal_score
                team.machinedesign_score = team.preliminary_machinedesign_score
                team.penalties_score = team.preliminary_penalties_score
                team.total_score = team.preliminary_total_score
                
                # Reset championship/redesign scores
                team.redesign_score = 0.0
                team.championship_score = 0.0
                team.advanced_to_championship = False
                team.championship_rank = None
                
                team.save()
            except Teams.DoesNotExist:
                continue
        
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
