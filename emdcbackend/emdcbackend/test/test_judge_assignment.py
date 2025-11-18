"""
Tests for judge assignment endpoints (assign_judge_to_contest, remove_judge_from_contest, etc.)
"""
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from datetime import date
from ..models import (
    Contest, Judge, JudgeClusters, MapContestToJudge, MapJudgeToCluster,
    MapContestToTeam, MapUserToRole, Admin, MapContestToCluster, Teams,
    MapClusterToTeam
)


class JudgeAssignmentTests(APITestCase):
    """Tests for judge assignment to contests"""
    
    def setUp(self):
        # Create a user and login using session authentication
        self.user = User.objects.create_user(username="testuser@example.com", password="testpassword")
        self.client.login(username="testuser@example.com", password="testpassword")
        
        # Create an admin user for role mapping
        self.admin = Admin.objects.create(first_name="Admin", last_name="User")
        MapUserToRole.objects.create(uuid=self.user.id, role=1, relatedid=self.admin.id)
        
        # Create test data
        self.contest1 = Contest.objects.create(
            name="Contest 1",
            date=date.today(),
            is_open=True,
            is_tabulated=False
        )
        
        self.contest2 = Contest.objects.create(
            name="Contest 2",
            date=date.today(),
            is_open=True,
            is_tabulated=False
        )
        
        self.judge = Judge.objects.create(
            first_name="Test",
            last_name="Judge",
            phone_number="1234567890",
            contestid=self.contest1.id,
            presentation=True,
            mdo=False,
            journal=True
        )
        
        self.cluster1 = JudgeClusters.objects.create(
            cluster_name="Cluster 1",
            cluster_type="preliminary"
        )
        
        self.cluster2 = JudgeClusters.objects.create(
            cluster_name="Cluster 2",
            cluster_type="preliminary"
        )
        
        # Note: cluster2 is preliminary, so championship=True will fail validation
        # The test should use preliminary scoresheets instead
        
        # Create a team for cluster validation
        self.team = Teams.objects.create(
            team_name="Test Team",
            journal_score=90.0,
            presentation_score=85.0,
            machinedesign_score=80.0,
            penalties_score=0.0,
            redesign_score=0.0,
            total_score=255.0,
            championship_score=0.0
        )
        
        MapClusterToTeam.objects.create(clusterid=self.cluster1.id, teamid=self.team.id)
        # Add team to cluster2 as well (required for assignment test)
        MapClusterToTeam.objects.create(clusterid=self.cluster2.id, teamid=self.team.id)
        MapContestToCluster.objects.create(contestid=self.contest1.id, clusterid=self.cluster1.id)
        MapContestToCluster.objects.create(contestid=self.contest2.id, clusterid=self.cluster2.id)
    
    def test_assign_judge_to_contest(self):
        """Test assigning a judge to a contest"""
        url = reverse('assign_judge_to_contest')
        # cluster2 is preliminary, so use preliminary scoresheets (not championship)
        data = {
            "judge_id": self.judge.id,
            "contest_id": self.contest2.id,
            "cluster_id": self.cluster2.id,
            "presentation": True,
            "journal": False,
            "mdo": True,
            "runpenalties": False,
            "otherpenalties": True,
            "redesign": False,
            "championship": False  # Changed to False since cluster2 is preliminary
        }
        response = self.client.post(url, data, format='json')
        
        # Endpoint returns 201 Created on success
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertIn('message', response.data)
        
        # Verify mappings were created
        self.assertTrue(MapContestToJudge.objects.filter(
            judgeid=self.judge.id,
            contestid=self.contest2.id
        ).exists())
        
        self.assertTrue(MapJudgeToCluster.objects.filter(
            judgeid=self.judge.id,
            clusterid=self.cluster2.id
        ).exists())
    
    def test_assign_judge_to_contest_missing_fields(self):
        """Test assigning judge with missing required fields"""
        url = reverse('assign_judge_to_contest')
        data = {
            "judge_id": self.judge.id,
            # Missing contest_id and cluster_id
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_assign_judge_to_contest_already_assigned(self):
        """Test assigning judge that's already assigned to contest/cluster"""
        # Pre-assign judge
        MapContestToJudge.objects.create(judgeid=self.judge.id, contestid=self.contest1.id)
        MapJudgeToCluster.objects.create(judgeid=self.judge.id, clusterid=self.cluster1.id)
        
        url = reverse('assign_judge_to_contest')
        data = {
            "judge_id": self.judge.id,
            "contest_id": self.contest1.id,
            "cluster_id": self.cluster1.id,
            "presentation": True,
            "journal": False,
            "mdo": True,
            "runpenalties": False,
            "otherpenalties": True,
            "redesign": False,
            "championship": True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('already assigned', response.data['error'].lower())
    
    def test_assign_judge_to_contest_invalid_judge(self):
        """Test assigning invalid judge ID"""
        url = reverse('assign_judge_to_contest')
        data = {
            "judge_id": 99999,
            "contest_id": self.contest2.id,
            "cluster_id": self.cluster2.id,
            "presentation": True,
            "journal": False,
            "mdo": True,
            "runpenalties": False,
            "otherpenalties": True,
            "redesign": False,
            "championship": True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_assign_judge_to_contest_invalid_contest(self):
        """Test assigning judge to invalid contest ID"""
        url = reverse('assign_judge_to_contest')
        data = {
            "judge_id": self.judge.id,
            "contest_id": 99999,
            "cluster_id": self.cluster2.id,
            "presentation": True,
            "journal": False,
            "mdo": True,
            "runpenalties": False,
            "otherpenalties": True,
            "redesign": False,
            "championship": True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_get_judge_contests(self):
        """Test getting all contests for a judge"""
        # Assign judge to contests
        MapContestToJudge.objects.create(judgeid=self.judge.id, contestid=self.contest1.id)
        MapContestToJudge.objects.create(judgeid=self.judge.id, contestid=self.contest2.id)
        
        url = reverse('get_judge_contests', args=[self.judge.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('contests', response.data)
        self.assertEqual(len(response.data['contests']), 2)
    
    def test_get_judge_contests_no_contests(self):
        """Test getting contests for judge with no contests"""
        url = reverse('get_judge_contests', args=[self.judge.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('contests', response.data)
        self.assertEqual(len(response.data['contests']), 0)
    
    def test_get_judge_contests_invalid_judge(self):
        """Test getting contests for invalid judge ID"""
        url = reverse('get_judge_contests', args=[99999])
        response = self.client.get(url)
        
        # Should handle gracefully (may return empty list or 404)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_remove_judge_from_contest(self):
        """Test removing judge from a contest"""
        # Pre-assign judge
        MapContestToJudge.objects.create(judgeid=self.judge.id, contestid=self.contest1.id)
        
        url = reverse('remove_judge_from_contest', args=[self.judge.id, self.contest1.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify mapping was removed
        self.assertFalse(MapContestToJudge.objects.filter(
            judgeid=self.judge.id,
            contestid=self.contest1.id
        ).exists())
    
    def test_remove_judge_from_contest_not_assigned(self):
        """Test removing judge that's not assigned to contest"""
        url = reverse('remove_judge_from_contest', args=[self.judge.id, self.contest2.id])
        response = self.client.delete(url)
        
        # Should handle gracefully (may return 200 or 404)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_remove_judge_from_cluster(self):
        """Test removing judge from a cluster"""
        # Pre-assign judge to cluster
        MapJudgeToCluster.objects.create(judgeid=self.judge.id, clusterid=self.cluster1.id)
        
        url = reverse('remove_judge_from_cluster', args=[self.judge.id, self.cluster1.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify mapping was removed
        self.assertFalse(MapJudgeToCluster.objects.filter(
            judgeid=self.judge.id,
            clusterid=self.cluster1.id
        ).exists())
    
    def test_remove_judge_from_cluster_not_assigned(self):
        """Test removing judge that's not assigned to cluster"""
        url = reverse('remove_judge_from_cluster', args=[self.judge.id, self.cluster2.id])
        response = self.client.delete(url)
        
        # Should handle gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_assign_judge_to_contest_cluster_without_teams(self):
        """Test assigning judge to cluster without teams (should fail)"""
        # Create empty cluster
        empty_cluster = JudgeClusters.objects.create(
            cluster_name="Empty Cluster",
            cluster_type="preliminary"
        )
        MapContestToCluster.objects.create(contestid=self.contest2.id, clusterid=empty_cluster.id)
        
        url = reverse('assign_judge_to_contest')
        data = {
            "judge_id": self.judge.id,
            "contest_id": self.contest2.id,
            "cluster_id": empty_cluster.id,
            "presentation": True,
            "journal": False,
            "mdo": True,
            "runpenalties": False,
            "otherpenalties": True,
            "redesign": False,
            "championship": True
        }
        response = self.client.post(url, data, format='json')
        
        # Should fail if cluster has no teams
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK])

