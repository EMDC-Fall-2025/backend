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
from django.db import models
from django.shortcuts import get_object_or_404
from ...models import JudgeClusters, Judge, MapJudgeToCluster, MapContestToCluster, MapScoresheetToTeamJudge, Scoresheet, MapClusterToTeam
from django.db import transaction
from ...serializers import JudgeClustersSerializer, JudgeSerializer, ClusterToJudgeSerializer


@api_view(["POST"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_cluster_judge_mapping(request):
    try:
        map_data = request.data
        result = map_cluster_to_judge(map_data)
        return Response(result, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def judges_by_cluster_id(request, cluster_id):
    mappings = MapJudgeToCluster.objects.filter(clusterid=cluster_id)
    judge_ids = mappings.values_list('judgeid', flat=True)
    judges = Judge.objects.filter(id__in=judge_ids)

    serializer = JudgeSerializer(judges, many=True)

    return Response({"Judges": serializer.data}, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def cluster_by_judge_id(request, judge_id):
    try:
        
        # Get all cluster mappings for this judge (judge can be in multiple clusters)
        mappings = MapJudgeToCluster.objects.filter(judgeid=judge_id)
        
        if not mappings.exists():
            return Response({"error": "No clusters found for the given judge"}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all clusters for this judge
        cluster_ids = mappings.values_list('clusterid', flat=True)
        clusters = JudgeClusters.objects.filter(id__in=cluster_ids)
        
        # Filter by active status if the field exists
        try:
            test_cluster = clusters.first()
            if test_cluster and hasattr(test_cluster, 'is_active'):
                clusters = clusters.filter(
                    models.Q(is_active=True) | models.Q(is_active__isnull=True)
                )
            else:
                pass
        except Exception as filter_error:
            pass
        
        # Return the first active cluster (for backward compatibility)
        if clusters.exists():
            cluster = clusters.first()
            serializer = JudgeClustersSerializer(instance=cluster)
            return Response({"Cluster": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "No active clusters found for the given judge"}, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def all_clusters_by_judge_id(request, judge_id):
    """Get all clusters for a judge across all contests"""
    try:
        
        mappings = MapJudgeToCluster.objects.filter(judgeid=judge_id)
        cluster_ids = mappings.values_list('clusterid', flat=True)
        
        # Get all clusters for this judge
        clusters = JudgeClusters.objects.filter(id__in=cluster_ids)
        
        # Filter by is_active status (now that field exists)
        clusters = clusters.filter(is_active=True)
        
        serializer = JudgeClustersSerializer(clusters, many=True)
        cluster_data = serializer.data
        
        # Add contest information to each cluster
        for cluster in cluster_data:
            try:
                contest_mapping = MapContestToCluster.objects.filter(clusterid=cluster['id']).first()
                if contest_mapping:
                    cluster['contest_id'] = contest_mapping.contestid
                else:
                    cluster['contest_id'] = None
            except Exception as e:
                cluster['contest_id'] = None
        
        
        return Response({"Clusters": cluster_data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _delete_cluster_judge_mapping_and_scores(map_id: int):
    """Delete a MapJudgeToCluster mapping and all related judge->team scoresheets for that cluster."""
    with transaction.atomic():
        mapping = get_object_or_404(MapJudgeToCluster, id=map_id)
        judge_id = mapping.judgeid
        cluster_id = mapping.clusterid

        team_ids = list(MapClusterToTeam.objects.filter(clusterid=cluster_id).values_list('teamid', flat=True))
        if team_ids:
            score_map_qs = MapScoresheetToTeamJudge.objects.filter(judgeid=judge_id, teamid__in=team_ids)
            scoresheet_ids = list(score_map_qs.values_list('scoresheetid', flat=True))
            # Delete mappings first, then scoresheets
            score_map_qs.delete()
            if scoresheet_ids:
                Scoresheet.objects.filter(id__in=scoresheet_ids).delete()

        # Finally delete the judge<->cluster mapping
        mapping.delete()


@api_view(["DELETE"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_cluster_judge_mapping_by_id(request, map_id):
    _delete_cluster_judge_mapping_and_scores(map_id)
    return Response({"detail": "Cluster To Judge Mapping deleted successfully."}, status=status.HTTP_200_OK)


def map_cluster_to_judge(map_data):
    # Check for existing mappings to prevent duplicates
    existing = MapJudgeToCluster.objects.filter(
        judgeid=map_data["judgeid"],
        clusterid=map_data["clusterid"]
    )
    if existing.exists():
        # Return existing mapping data instead of creating duplicate
        serializer = ClusterToJudgeSerializer(existing.first())
        return serializer.data
    
    serializer = ClusterToJudgeSerializer(data=map_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data
    else:
        raise ValidationError(serializer.errors)
    