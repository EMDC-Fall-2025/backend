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
    print("=" * 50)
    print("CHAMPIONSHIP ADVANCEMENT API CALLED!")
    print("=" * 50)
    """
    Activate championship and redesign clusters and move teams:
    1. Find existing championship and redesign clusters for the contest
    2. Activate them (set is_active=True)
    3. Move selected teams to championship cluster with modified names
    4. Move non-selected teams to redesign cluster with modified names
    5. Judges will now see the championship/redesign teams
    
    Body: { 
        "contestid": <int>, 
        "championship_team_ids": [1,2,3,...]  # Teams advancing to championship
    }
    """
    print("DEBUG: Request data received:", request.data)
    contest_id = request.data.get("contestid")
    championship_team_ids = request.data.get("championship_team_ids", [])
    print("DEBUG: Extracted contest_id:", contest_id)
    print("DEBUG: Extracted championship_team_ids:", championship_team_ids)

    if not contest_id:
        print("DEBUG: No contest_id provided")
        return Response({"ok": False, "message": "contestid is required"}, status=400)
    if not isinstance(championship_team_ids, list):
        print("DEBUG: championship_team_ids is not a list:", type(championship_team_ids))
        return Response({"ok": False, "message": "championship_team_ids must be a list"}, status=400)

    # Security check
    if not _ensure_requester_is_organizer_of_contest(request.user, contest_id):
        return Response({"ok": False, "message": "Organizer of this contest required."}, status=403)

    try:
        print(f"DEBUG: Starting championship advancement for contest {contest_id}")
        print(f"DEBUG: Championship team IDs: {championship_team_ids}")
        
        # 1. Set preliminary results
        contest_team_ids = list(
            MapContestToTeam.objects.filter(contestid=contest_id).values_list("teamid", flat=True)
        )
        print(f"DEBUG: Found {len(contest_team_ids)} teams in contest")
        
        # Reset all teams in contest
        Teams.objects.filter(id__in=contest_team_ids).update(
            advanced_to_championship=False, 
            championship_rank=None
        )
        
        # Set championship teams
        print(f"DEBUG: Championship team IDs from request: {championship_team_ids}")
        print(f"DEBUG: Contest team IDs: {contest_team_ids}")
        valid_championship_teams = [tid for tid in championship_team_ids if tid in contest_team_ids]
        print(f"DEBUG: Valid championship teams after filtering: {valid_championship_teams}")
        
        if valid_championship_teams:
            updated_count = Teams.objects.filter(id__in=valid_championship_teams).update(advanced_to_championship=True)
            print(f"DEBUG: Updated {updated_count} teams with advanced_to_championship=True")
            
            # Verify the update worked
            for team_id in valid_championship_teams:
                try:
                    team = Teams.objects.get(id=team_id)
                    print(f"DEBUG: Team {team_id} ({team.team_name}) advanced_to_championship: {team.advanced_to_championship}")
                except Teams.DoesNotExist:
                    print(f"DEBUG: Team {team_id} not found")
        else:
            print(f"DEBUG: No valid championship teams found - no teams will be marked as advanced")
        
        # Get non-championship teams
        non_championship_teams = [tid for tid in contest_team_ids if tid not in valid_championship_teams]
        print(f"DEBUG: Non-championship teams: {non_championship_teams}")
        
        # 2. Find existing championship and redesign clusters for this contest
        contest_clusters = MapContestToCluster.objects.filter(contestid=contest_id)
        print(f"DEBUG: Found {len(contest_clusters)} clusters for contest")
        championship_cluster = None
        redesign_cluster = None
        
        for cc in contest_clusters:
            try:
                cluster = JudgeClusters.objects.get(id=cc.clusterid)
                print(f"DEBUG: Checking cluster {cluster.id} - {cluster.cluster_name} - type: {getattr(cluster, 'cluster_type', 'NO_TYPE_FIELD')}")
                
                # Check by cluster_type field first (if it exists and is not default)
                cluster_type = getattr(cluster, 'cluster_type', None)
                if cluster_type and cluster_type != 'preliminary':
                    if cluster_type == 'championship':
                        championship_cluster = cluster
                        print(f"DEBUG: Found championship cluster by type: {cluster.id}")
                    elif cluster_type == 'redesign':
                        redesign_cluster = cluster
                        print(f"DEBUG: Found redesign cluster by type: {cluster.id}")
                # Fallback: check by name if cluster_type field doesn't exist or is preliminary
                else:
                    if 'championship' in cluster.cluster_name.lower():
                        championship_cluster = cluster
                        print(f"DEBUG: Found championship cluster by name: {cluster.id}")
                    elif 'redesign' in cluster.cluster_name.lower():
                        redesign_cluster = cluster
                        print(f"DEBUG: Found redesign cluster by name: {cluster.id}")
            except JudgeClusters.DoesNotExist:
                print(f"DEBUG: Cluster {cc.clusterid} does not exist")
                continue
        
        if not championship_cluster:
            return Response({"ok": False, "message": "Championship cluster not found. Please create it first."}, status=400)
        if not redesign_cluster:
            return Response({"ok": False, "message": "Redesign cluster not found. Please create it first."}, status=400)
        
        # 3. Activate the clusters (THIS IS WHERE THEY BECOME ACTIVE!)
        if hasattr(championship_cluster, 'is_active'):
            championship_cluster.is_active = True
            championship_cluster.save()
            print(f"DEBUG: Activated championship cluster {championship_cluster.id}")
        else:
            print(f"DEBUG: is_active field not available for championship cluster {championship_cluster.id}")
            
        if hasattr(redesign_cluster, 'is_active'):
            redesign_cluster.is_active = True
            redesign_cluster.save()
            print(f"DEBUG: Activated redesign cluster {redesign_cluster.id}")
        else:
            print(f"DEBUG: is_active field not available for redesign cluster {redesign_cluster.id}")
        
        # 4. Clear existing team assignments from these clusters
        print(f"DEBUG: Clearing existing team assignments from championship cluster {championship_cluster.id}")
        championship_deleted = MapClusterToTeam.objects.filter(clusterid=championship_cluster.id).delete()
        print(f"DEBUG: Deleted {championship_deleted[0]} existing team mappings from championship cluster")
        
        print(f"DEBUG: Clearing existing team assignments from redesign cluster {redesign_cluster.id}")
        redesign_deleted = MapClusterToTeam.objects.filter(clusterid=redesign_cluster.id).delete()
        print(f"DEBUG: Deleted {redesign_deleted[0]} existing team mappings from redesign cluster")
        
        # 5. Assign teams to clusters (keep original teams, just move them)
        championship_teams_data = []
        redesign_teams_data = []
        
        # Championship teams - move existing teams to championship cluster
        print(f"DEBUG: Processing {len(valid_championship_teams)} championship teams: {valid_championship_teams}")
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
                mapping = MapClusterToTeam.objects.create(clusterid=championship_cluster.id, teamid=team.id)
                print(f"DEBUG: Created team mapping: cluster {championship_cluster.id} -> team {team.id} (mapping ID: {mapping.id})")
                
                # Verify the mapping was created
                verification = MapClusterToTeam.objects.filter(clusterid=championship_cluster.id, teamid=team.id)
                print(f"DEBUG: Verification - found {verification.count()} mappings for team {team.id} in cluster {championship_cluster.id}")
            except Teams.DoesNotExist:
                continue
        
        # Redesign teams - move existing teams to redesign cluster
        print(f"DEBUG: Processing {len(non_championship_teams)} redesign teams: {non_championship_teams}")
        for team_id in non_championship_teams:
            try:
                team = Teams.objects.get(id=team_id)
                # Reset scores for redesign round (except journal score)
                team.presentation_score = 0.0
                team.machinedesign_score = 0.0
                team.penalties_score = 0.0
                team.redesign_score = 0.0
                team.championship_score = 0.0
                # Keep journal_score from preliminary round
                # Let tabulation system calculate total_score properly
                team.save()
                
                redesign_teams_data.append(team)
                mapping = MapClusterToTeam.objects.create(clusterid=redesign_cluster.id, teamid=team.id)
                print(f"DEBUG: Created team mapping: cluster {redesign_cluster.id} -> team {team.id} (mapping ID: {mapping.id})")
                
                # Verify the mapping was created
                verification = MapClusterToTeam.objects.filter(clusterid=redesign_cluster.id, teamid=team.id)
                print(f"DEBUG: Verification - found {verification.count()} mappings for team {team.id} in cluster {redesign_cluster.id}")
            except Teams.DoesNotExist:
                continue
        
        # 6. Update judge flags for championship/redesign clusters
        from ..models import MapJudgeToCluster, Judge
        
        # Update judges in championship cluster to have championship=True
        championship_judge_mappings = MapJudgeToCluster.objects.filter(clusterid=championship_cluster.id)
        print(f"DEBUG: Found {championship_judge_mappings.count()} judges in championship cluster {championship_cluster.id}")
        
        for mapping in championship_judge_mappings:
            try:
                judge = Judge.objects.get(id=mapping.judgeid)
                print(f"DEBUG: Processing judge {judge.id} ({judge.first_name} {judge.last_name})")
                print(f"DEBUG: Current championship flag: {judge.championship}")
                if not judge.championship:
                    judge.championship = True
                    judge.save()
                    print(f"DEBUG: Set championship=True for judge {judge.id} ({judge.first_name} {judge.last_name})")
                else:
                    print(f"DEBUG: Judge {judge.id} already has championship=True")
            except Judge.DoesNotExist:
                print(f"DEBUG: Judge {mapping.judgeid} not found")
                continue
        
        # Update judges in redesign cluster to have redesign=True
        redesign_judge_mappings = MapJudgeToCluster.objects.filter(clusterid=redesign_cluster.id)
        print(f"DEBUG: Found {redesign_judge_mappings.count()} judges in redesign cluster {redesign_cluster.id}")
        
        for mapping in redesign_judge_mappings:
            try:
                judge = Judge.objects.get(id=mapping.judgeid)
                print(f"DEBUG: Processing redesign judge {judge.id} ({judge.first_name} {judge.last_name})")
                print(f"DEBUG: Current redesign flag: {judge.redesign}")
                if not judge.redesign:
                    judge.redesign = True
                    judge.save()
                    print(f"DEBUG: Set redesign=True for judge {judge.id} ({judge.first_name} {judge.last_name})")
                else:
                    print(f"DEBUG: Judge {judge.id} already has redesign=True")
            except Judge.DoesNotExist:
                print(f"DEBUG: Judge {mapping.judgeid} not found")
                continue
        
        # 7. Clear existing championship/redesign scoresheets to avoid duplicates
        from ..models import MapScoresheetToTeamJudge, Scoresheet
        
        # Clear championship cluster scoresheets (types 6 and 7)
        championship_judge_ids = [mapping.judgeid for mapping in championship_judge_mappings]
        if championship_judge_ids:
            championship_scoresheets_to_delete = MapScoresheetToTeamJudge.objects.filter(
                judgeid__in=championship_judge_ids,
                sheetType__in=[6, 7]  # redesign and championship scoresheets
            )
            print(f"DEBUG: Found {championship_scoresheets_to_delete.count()} existing championship scoresheets to delete")
            championship_scoresheets_to_delete.delete()
        
        # Clear redesign cluster scoresheets (types 6 and 7)
        redesign_judge_ids = [mapping.judgeid for mapping in redesign_judge_mappings]
        if redesign_judge_ids:
            redesign_scoresheets_to_delete = MapScoresheetToTeamJudge.objects.filter(
                judgeid__in=redesign_judge_ids,
                sheetType__in=[6, 7]  # redesign and championship scoresheets
            )
            print(f"DEBUG: Found {redesign_scoresheets_to_delete.count()} existing redesign scoresheets to delete")
            redesign_scoresheets_to_delete.delete()
        
        # 8. Create scoresheets for judges in the new clusters
        from .scoresheets import create_scoresheets_for_judges_in_cluster
        
        # Create scoresheets for championship cluster
        print(f"DEBUG: Creating scoresheets for championship cluster {championship_cluster.id}")
        print(f"DEBUG: Championship cluster has {championship_teams_data.__len__()} teams")
        
        # Verify team mappings exist before creating scoresheets
        championship_team_mappings = MapClusterToTeam.objects.filter(clusterid=championship_cluster.id)
        print(f"DEBUG: Before scoresheet creation - found {championship_team_mappings.count()} team mappings in championship cluster")
        
        try:
            championship_scoresheets = create_scoresheets_for_judges_in_cluster(championship_cluster.id)
            print(f"DEBUG: Created {len(championship_scoresheets)} scoresheets for championship cluster")
            print(f"DEBUG: Championship scoresheets details: {championship_scoresheets}")
        except Exception as e:
            print(f"DEBUG: Error creating scoresheets for championship cluster: {str(e)}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        
        # Create scoresheets for redesign cluster
        print(f"DEBUG: Creating scoresheets for redesign cluster {redesign_cluster.id}")
        print(f"DEBUG: Redesign cluster has {redesign_teams_data.__len__()} teams")
        
        # Verify team mappings exist before creating scoresheets
        redesign_team_mappings = MapClusterToTeam.objects.filter(clusterid=redesign_cluster.id)
        print(f"DEBUG: Before scoresheet creation - found {redesign_team_mappings.count()} team mappings in redesign cluster")
        
        try:
            redesign_scoresheets = create_scoresheets_for_judges_in_cluster(redesign_cluster.id)
            print(f"DEBUG: Created {len(redesign_scoresheets)} scoresheets for redesign cluster")
            print(f"DEBUG: Redesign scoresheets details: {redesign_scoresheets}")
        except Exception as e:
            print(f"DEBUG: Error creating scoresheets for redesign cluster: {str(e)}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        
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
                cluster_type = getattr(cluster, 'cluster_type', None)
                if cluster_type == 'championship' or 'championship' in cluster.cluster_name.lower():
                    championship_cluster = cluster
                elif cluster_type == 'redesign' or 'redesign' in cluster.cluster_name.lower():
                    redesign_cluster = cluster
            except JudgeClusters.DoesNotExist:
                continue
        
        # 3. Deactivate clusters
        if championship_cluster and hasattr(championship_cluster, 'is_active'):
            championship_cluster.is_active = False
            championship_cluster.save()
            
        if redesign_cluster and hasattr(redesign_cluster, 'is_active'):
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