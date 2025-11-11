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
from ...models import MapScoresheetToTeamJudge, Scoresheet, MapContestToJudge, MapJudgeToCluster, MapClusterToTeam, MapContestToCluster
from ...serializers import MapScoreSheetToTeamJudgeSerializer, ScoresheetSerializer


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_score_sheet_mapping(request):
    try:
        result = map_score_sheet(request.data)
        return Response(result, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def score_sheet_by_judge_team(request, judge_id, team_id, sheetType):
    try:
        # Get all mappings for this specific team/judge/sheetType combination
        mappings = MapScoresheetToTeamJudge.objects.filter(
            judgeid=judge_id, 
            teamid=team_id, 
            sheetType=sheetType
        ).order_by('id')
        
        if not mappings.exists():
            return Response({"error": "No mapping found for the provided judge, team, and sheet type."},
                            status=status.HTTP_404_NOT_FOUND)
        
        # If multiple mappings exist, prioritize submitted scoresheets, then most recent
        if mappings.count() > 1:
            best_mapping = None
            
            for mapping in mappings:
                try:
                    scoresheet = Scoresheet.objects.get(id=mapping.scoresheetid)
                    is_submitted = scoresheet.isSubmitted
                    
                    if best_mapping is None:
                        best_mapping = mapping
                    else:
                        # Check if current mapping is submitted and existing is not
                        try:
                            existing_scoresheet = Scoresheet.objects.get(id=best_mapping.scoresheetid)
                            existing_submitted = existing_scoresheet.isSubmitted
                        except:
                            existing_submitted = False
                        
                        if is_submitted and not existing_submitted:
                            best_mapping = mapping
                        elif not is_submitted and existing_submitted:
                            pass  # Keep existing submitted mapping
                        elif mapping.id > best_mapping.id:
                            best_mapping = mapping
                            
                except Scoresheet.DoesNotExist:
                    continue
            
            if best_mapping is None:
                return Response({"error": "No valid scoresheet found for the provided judge, team, and sheet type."},
                                status=status.HTTP_404_NOT_FOUND)
            
            mapping = best_mapping
        else:
            mapping = mappings.first()
        
        sheet = Scoresheet.objects.get(id=mapping.scoresheetid)
        serializer = ScoresheetSerializer(instance=sheet)
        return Response({"ScoreSheet": serializer.data}, status=status.HTTP_200_OK)

    except MapScoresheetToTeamJudge.DoesNotExist:
        return Response({"error": "No mapping found for the provided judge, team, and sheet type."},
                        status=status.HTTP_404_NOT_FOUND)

    except Scoresheet.DoesNotExist:
        return Response({"error": "Scoresheet not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def score_sheets_by_judge(request, judge_id):
    try:
        # Fetch mappings for the given judge
        mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id)

        if not mappings.exists():
            # Return empty list instead of 404 to simplify client handling
            return Response({"ScoreSheets": []}, status=status.HTTP_200_OK)

        # Prepare data to return mappings with scoresheets
        results = []
        for mapping in mappings:
            # Fetch the scoresheet by its ID
            try:
                score_sheet = Scoresheet.objects.get(id=mapping.scoresheetid)
                serializer = ScoresheetSerializer(score_sheet).data
                total_score = 0
                if mapping.sheetType == 4:
                    total_score = (serializer.get("field1") + serializer.get("field2") + serializer.get("field3") +
                           serializer.get("field4") + serializer.get("field5") + serializer.get("field6") +
                           serializer.get("field7") + serializer.get("field8") + serializer.get("field10") +
                           serializer.get("field11") + serializer.get("field12") + serializer.get("field13") +
                           serializer.get("field14") + serializer.get("field15") + serializer.get("field16") +
                           serializer.get("field17"))
                elif mapping.sheetType == 5:
                    total_score = (serializer.get("field1") + serializer.get("field2") + serializer.get("field3") +
                                   serializer.get("field4") + serializer.get("field5") + serializer.get("field6") +
                                   serializer.get("field7"))
                elif mapping.sheetType == 6:
                    total_score = (serializer.get("field1") + serializer.get("field2") + serializer.get("field3") +
                                   serializer.get("field4") + serializer.get("field5") + serializer.get("field6") +
                                   serializer.get("field7"))
                else:
                    total_score = (serializer.get("field1")+serializer.get("field2")+serializer.get("field3")+
                                  serializer.get("field4")+serializer.get("field5")+serializer.get("field6")+
                                  serializer.get("field7")+serializer.get("field8"))
                results.append({
                    "mapping": {
                        "teamid": mapping.teamid,
                        "judgeid": mapping.judgeid,
                        "scoresheetid": mapping.scoresheetid,
                        "sheetType": mapping.sheetType,
                    },
                    "scoresheet": serializer,  # Serialize the scoresheet
                    "total": total_score
                })
            except Scoresheet.DoesNotExist:
                results.append({
                    "mapping": {
                        "teamid": mapping.teamid,
                        "judgeid": mapping.judgeid,
                        "scoresheetid": mapping.scoresheetid,
                        "sheetType": mapping.sheetType,
                    },
                    "scoresheet": None  # Or handle this case as needed
                })

        return Response({"ScoreSheets": results}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def score_sheets_by_judge_and_cluster(request, judge_id, cluster_id):
    """
    Fetch scoresheets for a specific judge within a specific cluster.
    This is used to filter scoresheets by cluster type (championship/redesign).
    """
    try:
        # Get all teams in the cluster
        cluster_team_mappings = MapClusterToTeam.objects.filter(clusterid=cluster_id)
        team_ids = cluster_team_mappings.values_list('teamid', flat=True)
        
        # Fetch mappings for the judge and teams in this cluster only
        mappings = MapScoresheetToTeamJudge.objects.filter(
            judgeid=judge_id,
            teamid__in=team_ids
        )

        if not mappings.exists():
            # Return empty list instead of 404 to simplify client handling
            return Response({"ScoreSheets": []}, status=status.HTTP_200_OK)

        # Prepare data to return mappings with scoresheets
        results = []
        for mapping in mappings:
            # Fetch the scoresheet by its ID
            try:
                score_sheet = Scoresheet.objects.get(id=mapping.scoresheetid)
                serializer = ScoresheetSerializer(score_sheet).data
                total_score = 0
                if mapping.sheetType == 4:
                    total_score = (serializer.get('field1', 0) or 0) + (serializer.get('field2', 0) or 0) + (serializer.get('field3', 0) or 0) + (serializer.get('field4', 0) or 0) + (serializer.get('field5', 0) or 0) + (serializer.get('field6', 0) or 0) + (serializer.get('field7', 0) or 0) + (serializer.get('field8', 0) or 0) + (serializer.get('field10', 0) or 0) + (serializer.get('field11', 0) or 0) + (serializer.get('field12', 0) or 0) + (serializer.get('field13', 0) or 0) + (serializer.get('field14', 0) or 0) + (serializer.get('field15', 0) or 0) + (serializer.get('field16', 0) or 0) + (serializer.get('field17', 0) or 0)
                elif mapping.sheetType == 5:
                    total_score = (serializer.get('field1', 0) or 0) + (serializer.get('field2', 0) or 0) + (serializer.get('field3', 0) or 0) + (serializer.get('field4', 0) or 0) + (serializer.get('field5', 0) or 0) + (serializer.get('field6', 0) or 0) + (serializer.get('field7', 0) or 0)
                elif mapping.sheetType == 1:
                    total_score = (serializer.get('field1', 0) or 0) + (serializer.get('field2', 0) or 0) + (serializer.get('field3', 0) or 0) + (serializer.get('field4', 0) or 0) + (serializer.get('field5', 0) or 0) + (serializer.get('field6', 0) or 0) + (serializer.get('field7', 0) or 0) + (serializer.get('field8', 0) or 0)
                elif mapping.sheetType == 2:
                    total_score = (serializer.get('field1', 0) or 0) + (serializer.get('field2', 0) or 0) + (serializer.get('field3', 0) or 0) + (serializer.get('field4', 0) or 0) + (serializer.get('field5', 0) or 0) + (serializer.get('field6', 0) or 0) + (serializer.get('field7', 0) or 0) + (serializer.get('field8', 0) or 0)
                elif mapping.sheetType == 3:
                    total_score = (serializer.get('field1', 0) or 0) + (serializer.get('field2', 0) or 0) + (serializer.get('field3', 0) or 0) + (serializer.get('field4', 0) or 0) + (serializer.get('field5', 0) or 0) + (serializer.get('field6', 0) or 0) + (serializer.get('field7', 0) or 0) + (serializer.get('field8', 0) or 0)
                elif mapping.sheetType == 6:
                    total_score = (serializer.get('field1', 0) or 0) + (serializer.get('field2', 0) or 0) + (serializer.get('field3', 0) or 0) + (serializer.get('field4', 0) or 0) + (serializer.get('field5', 0) or 0) + (serializer.get('field6', 0) or 0) + (serializer.get('field7', 0) or 0) + (serializer.get('field8', 0) or 0)
                elif mapping.sheetType == 7:
                    total_score = (serializer.get('field1', 0) or 0) + (serializer.get('field2', 0) or 0) + (serializer.get('field3', 0) or 0) + (serializer.get('field4', 0) or 0) + (serializer.get('field5', 0) or 0) + (serializer.get('field6', 0) or 0) + (serializer.get('field7', 0) or 0) + (serializer.get('field8', 0) or 0) + (serializer.get('field9', 0) or 0)
                
                results.append({
                    "mapping": {
                        "id": mapping.id,
                        "teamid": mapping.teamid,
                        "judgeid": mapping.judgeid,
                        "scoresheetid": mapping.scoresheetid,
                        "sheetType": mapping.sheetType
                    },
                    "scoresheet": serializer,
                    "total": total_score
                })
            except Scoresheet.DoesNotExist:
                continue

        return Response({"ScoreSheets": results}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def all_sheets_submitted_for_contests(request):
    contests = request.data
    results = {}

    try:
        for contest in contests:
            contest_id = contest.get('id')
            
            # Get all clusters for this contest
            contest_cluster_mappings = MapContestToCluster.objects.filter(contestid=contest_id)
            cluster_ids = contest_cluster_mappings.values_list('clusterid', flat=True).distinct()
            
            if not cluster_ids:
                # No clusters in contest, so no judges to check
                results[contest_id] = True
                continue
            
            # Get all judges assigned to clusters in this contest
            judge_cluster_mappings = MapJudgeToCluster.objects.filter(clusterid__in=cluster_ids)
            judge_ids = judge_cluster_mappings.values_list('judgeid', flat=True).distinct()
            
            if not judge_ids:
                # No judges assigned to clusters in this contest
                results[contest_id] = True
                continue
            
            # Get all teams in clusters for this contest
            team_cluster_mappings = MapClusterToTeam.objects.filter(clusterid__in=cluster_ids)
            team_ids = team_cluster_mappings.values_list('teamid', flat=True).distinct()
            
            if not team_ids:
                # No teams in clusters, so no score sheets to check
                results[contest_id] = True
                continue
            
            # Check if all score sheets for judges and teams in this contest are submitted
            all_submitted = True
            
            for judge_id in judge_ids:
                # Get all score sheet mappings for this judge and teams in contest clusters
                score_sheet_mappings = MapScoresheetToTeamJudge.objects.filter(
                    judgeid=judge_id,
                    teamid__in=team_ids
                )
                
                if not score_sheet_mappings.exists():
                    # Judge has no score sheet mappings for teams in this contest
                    # This could mean they haven't been assigned yet, so consider as not submitted
                    all_submitted = False
                    break
                
                # Get all score sheet IDs for this judge's mappings in this contest
                scoresheet_ids = score_sheet_mappings.values_list('scoresheetid', flat=True)
                
                # Check if any score sheet is not submitted
                unsubmitted_count = Scoresheet.objects.filter(
                    id__in=scoresheet_ids,
                    isSubmitted=False
                ).count()
                
                if unsubmitted_count > 0:
                    all_submitted = False
                    break
            
            results[contest_id] = all_submitted

        return Response(results, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def submit_all_penalty_sheets_for_judge(request):
    try:
        penalty_mappings = MapScoresheetToTeamJudge.objects.filter(judgeid=request.data["judge_id"], sheetType=4)

        if not penalty_mappings.exists():
            return Response({"error": "No penalty score sheets found for the provided judge."},
                            status=status.HTTP_404_NOT_FOUND)

        for mapping in penalty_mappings:
            scoresheet = get_object_or_404(Scoresheet, id=mapping.scoresheetid)

            scoresheet.isSubmitted = True
            scoresheet.save()

        return Response(status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_score_sheet_mapping_by_id(request, map_id):
    map_to_delete = get_object_or_404(MapScoresheetToTeamJudge, id=map_id)
    map_to_delete.delete()
    return Response({"detail": "Mapping deleted successfully."}, status=status.HTTP_200_OK)


def delete_score_sheet_mapping(map_id):
    # python can't overload functions >:(
    map_to_delete = get_object_or_404(MapScoresheetToTeamJudge, id=map_id)
    map_to_delete.delete()
    return Response({"detail": "Mapping deleted successfully."}, status=status.HTTP_200_OK)


def map_score_sheet(map_data):
    serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data

    raise ValidationError(serializer.errors)


def map_score_sheets_for_team_in_cluster(team_id, cluster_id):
    # Fetch judges assigned to the cluster
    mappings = MapJudgeToCluster.objects.filter(clusterid=cluster_id)
    judge_ids = mappings.values_list('judgeid', flat=True)

    # Fetch scoresheets assigned to the team
    team_judge_mappings = MapScoresheetToTeamJudge.objects.filter(teamid=team_id, judgeid__in=judge_ids)
    scoresheet_ids = team_judge_mappings.values_list('scoresheetid', flat=True)

    # Fetch scoresheets for the team
    scoresheets = Scoresheet.objects.filter(id__in=scoresheet_ids)
    serializer = ScoresheetSerializer(scoresheets, many=True)

    return serializer.data


# Per-team submission status: how many assigned score sheets have been submitted
@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def all_submitted_for_team(request, team_id: int):
    try:
        mappings = MapScoresheetToTeamJudge.objects.filter(teamid=team_id)
        total = mappings.count()
        if total == 0:
            return Response({
                "teamId": team_id,
                "submittedCount": 0,
                "totalCount": 0,
                "allSubmitted": False,
            }, status=status.HTTP_200_OK)

        sheet_ids = mappings.values_list("scoresheetid", flat=True)
        submitted_count = Scoresheet.objects.filter(id__in=sheet_ids, isSubmitted=True).count()

        return Response({
            "teamId": team_id,
            "submittedCount": submitted_count,
            "totalCount": total,
            "allSubmitted": submitted_count == total,
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)