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
from ...models import JudgeClusters, Judge, MapJudgeToCluster, MapContestToCluster
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
        print(f"DEBUG: cluster_by_judge_id called for judge {judge_id}")
        
        # Get all cluster mappings for this judge (judge can be in multiple clusters)
        mappings = MapJudgeToCluster.objects.filter(judgeid=judge_id)
        print(f"DEBUG: Found {mappings.count()} cluster mappings for judge {judge_id}")
        
        if not mappings.exists():
            print(f"DEBUG: No cluster mappings found for judge {judge_id}")
            return Response({"error": "No clusters found for the given judge"}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all clusters for this judge
        cluster_ids = mappings.values_list('clusterid', flat=True)
        clusters = JudgeClusters.objects.filter(id__in=cluster_ids)
        print(f"DEBUG: Found {clusters.count()} clusters for judge {judge_id}")
        
        # Filter by active status if the field exists
        try:
            test_cluster = clusters.first()
            if test_cluster and hasattr(test_cluster, 'is_active'):
                print(f"DEBUG: is_active field exists, filtering by active status")
                clusters = clusters.filter(
                    models.Q(is_active=True) | models.Q(is_active__isnull=True)
                )
                print(f"DEBUG: After filtering by is_active: {clusters.count()} clusters")
            else:
                print(f"DEBUG: is_active field does not exist, returning all clusters")
        except Exception as filter_error:
            print(f"DEBUG: Error filtering by is_active: {str(filter_error)}, returning all clusters")
        
        # Return the first active cluster (for backward compatibility)
        if clusters.exists():
            cluster = clusters.first()
            print(f"DEBUG: Returning first cluster: {cluster.cluster_name}")
            serializer = JudgeClustersSerializer(instance=cluster)
            return Response({"Cluster": serializer.data}, status=status.HTTP_200_OK)
        else:
            print(f"DEBUG: No active clusters found for judge {judge_id}")
            return Response({"error": "No active clusters found for the given judge"}, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        print(f"DEBUG: Error in cluster_by_judge_id: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def all_clusters_by_judge_id(request, judge_id):
    """Get all clusters for a judge across all contests"""
    try:
        print(f"DEBUG: all_clusters_by_judge_id called for judge {judge_id}")
        
        mappings = MapJudgeToCluster.objects.filter(judgeid=judge_id)
        cluster_ids = mappings.values_list('clusterid', flat=True)
        print(f"DEBUG: Found {len(cluster_ids)} cluster mappings for judge {judge_id}")
        
        # Get all clusters for this judge
        clusters = JudgeClusters.objects.filter(id__in=cluster_ids)
        print(f"DEBUG: Found {clusters.count()} clusters in database")
        
        # Filter by is_active status if the field exists
        try:
            # Check if is_active field exists by trying to filter on it
            test_cluster = clusters.first()
            if test_cluster and hasattr(test_cluster, 'is_active'):
                print(f"DEBUG: is_active field exists, filtering by active status")
                clusters = clusters.filter(
                    models.Q(is_active=True) | models.Q(is_active__isnull=True)
                )
                print(f"DEBUG: After filtering by is_active: {clusters.count()} clusters")
            else:
                print(f"DEBUG: is_active field does not exist, returning all clusters")
        except Exception as filter_error:
            print(f"DEBUG: Error filtering by is_active: {str(filter_error)}, returning all clusters")
        
        serializer = JudgeClustersSerializer(clusters, many=True)
        cluster_data = serializer.data
        
        # Add contest information to each cluster
        for cluster in cluster_data:
            try:
                contest_mapping = MapContestToCluster.objects.filter(clusterid=cluster['id']).first()
                if contest_mapping:
                    cluster['contest_id'] = contest_mapping.contestid
                    print(f"DEBUG: Added contest_id {contest_mapping.contestid} to cluster {cluster['id']}")
                else:
                    cluster['contest_id'] = None
                    print(f"DEBUG: No contest mapping found for cluster {cluster['id']}")
            except Exception as e:
                print(f"DEBUG: Error getting contest for cluster {cluster['id']}: {str(e)}")
                cluster['contest_id'] = None
        
        print(f"DEBUG: Returning {len(cluster_data)} clusters for judge {judge_id}")
        
        return Response({"Clusters": cluster_data}, status=status.HTTP_200_OK)
    except Exception as e:
        print(f"DEBUG: Error in all_clusters_by_judge_id: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["DELETE"])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_cluster_judge_mapping_by_id(request, map_id):
    map_to_delete = get_object_or_404(MapJudgeToCluster, id=map_id)
    map_to_delete.delete()
    return Response({"detail": "Cluster To Judge Mapping deleted successfully."}, status=status.HTTP_200_OK)


def delete_cluster_judge_mapping(map_id):
    # python can't overload functions >:(
    map_to_delete = get_object_or_404(MapJudgeToCluster, id=map_id)
    map_to_delete.delete()
    return Response({"detail": "Cluster To Judge Mapping deleted successfully."}, status=status.HTTP_200_OK)


def map_cluster_to_judge(map_data):
    serializer = ClusterToJudgeSerializer(data=map_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data
    else:
        raise ValidationError(serializer.errors)
    
def judges_by_cluster(cluster_id):
    mappings = MapJudgeToCluster.objects.filter(clusterid=cluster_id)
    judge_ids = mappings.values_list('judgeid', flat=True)
    judges = Judge.objects.filter(id__in=judge_ids)

    serializer = JudgeSerializer(judges, many=True)

    return Response({"Judges": serializer.data}, status=status.HTTP_200_OK)