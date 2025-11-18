"""
Tests for missing mapping endpoints
"""
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from datetime import date
from ..models import (
    Contest, Teams, Judge, JudgeClusters, MapContestToTeam, MapContestToOrganizer,
    MapUserToRole, Organizer, Admin, MapClusterToTeam, MapJudgeToCluster,
    MapContestToCluster, Coach, MapCoachToTeam
)


class MissingMappingTests(APITestCase):
    """Tests for previously untested mapping endpoints"""
    
    def setUp(self):
        # Create a user and login using session authentication
        self.user = User.objects.create_user(username="testuser@example.com", password="testpassword")
        self.client.login(username="testuser@example.com", password="testpassword")
        
        # Create an admin user for role mapping
        self.admin = Admin.objects.create(first_name="Admin", last_name="User")
        MapUserToRole.objects.create(uuid=self.user.id, role=1, relatedid=self.admin.id)
        
        # Create test data
        self.contest = Contest.objects.create(
            name="Test Contest",
            date=date.today(),
            is_open=True,
            is_tabulated=False
        )
        
        self.contest2 = Contest.objects.create(
            name="Test Contest 2",
            date=date.today(),
            is_open=True,
            is_tabulated=False
        )
        
        self.judge = Judge.objects.create(
            first_name="Test",
            last_name="Judge",
            phone_number="1234567890",
            contestid=self.contest.id,
            presentation=True,
            mdo=False,
            journal=True
        )
        
        self.cluster = JudgeClusters.objects.create(
            cluster_name="Test Cluster",
            cluster_type="preliminary"
        )
        
        self.cluster2 = JudgeClusters.objects.create(
            cluster_name="Test Cluster 2",
            cluster_type="preliminary"
        )
        
        self.team1 = Teams.objects.create(
            team_name="Team 1",
            journal_score=90.0,
            presentation_score=85.0,
            machinedesign_score=80.0,
            penalties_score=0.0,
            redesign_score=0.0,
            total_score=255.0,
            championship_score=0.0
        )
        
        self.team2 = Teams.objects.create(
            team_name="Team 2",
            journal_score=88.0,
            presentation_score=82.0,
            machinedesign_score=78.0,
            penalties_score=0.0,
            redesign_score=0.0,
            total_score=248.0,
            championship_score=0.0
        )
        
        self.coach1 = Coach.objects.create(first_name="Coach", last_name="One")
        self.coach2 = Coach.objects.create(first_name="Coach", last_name="Two")
        
        self.organizer = Organizer.objects.create(first_name="Test", last_name="Organizer")
        
        # Create users for coaches (required for coaches_by_teams endpoint)
        self.coach1_user = User.objects.create_user(username="coach1@example.com", password="password")
        self.coach2_user = User.objects.create_user(username="coach2@example.com", password="password")
        MapUserToRole.objects.create(uuid=self.coach1_user.id, role=4, relatedid=self.coach1.id)
        MapUserToRole.objects.create(uuid=self.coach2_user.id, role=4, relatedid=self.coach2.id)
        
        # Create basic mappings
        MapContestToCluster.objects.create(contestid=self.contest.id, clusterid=self.cluster.id)
        MapContestToCluster.objects.create(contestid=self.contest.id, clusterid=self.cluster2.id)
        MapClusterToTeam.objects.create(clusterid=self.cluster.id, teamid=self.team1.id)
        MapClusterToTeam.objects.create(clusterid=self.cluster.id, teamid=self.team2.id)
        MapJudgeToCluster.objects.create(judgeid=self.judge.id, clusterid=self.cluster.id)
        MapContestToTeam.objects.create(contestid=self.contest.id, teamid=self.team1.id)
        MapContestToTeam.objects.create(contestid=self.contest.id, teamid=self.team2.id)
        MapContestToOrganizer.objects.create(contestid=self.contest.id, organizerid=self.organizer.id)
        MapCoachToTeam.objects.create(coachid=self.coach1.id, teamid=self.team1.id)
        MapCoachToTeam.objects.create(coachid=self.coach2.id, teamid=self.team2.id)
    
    def test_coaches_by_teams(self):
        """Test getting coaches by team IDs"""
        url = reverse('coaches_by_teams')
        # Endpoint expects a list of team objects with "id" field
        data = [
            {"id": self.team1.id},
            {"id": self.team2.id}
        ]
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
    
    def test_coaches_by_teams_empty_list(self):
        """Test getting coaches with empty team list"""
        url = reverse('coaches_by_teams')
        # Endpoint expects a list of team objects
        data = []
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
    
    def test_get_contests_by_team_ids(self):
        """Test getting contests by team IDs"""
        url = reverse('get_contests_by_team_ids')
        # Endpoint expects a list of team objects with "id" field
        data = [
            {"id": self.team1.id},
            {"id": self.team2.id}
        ]
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
    
    def test_get_contests_by_team_ids_empty(self):
        """Test getting contests with empty team list"""
        url = reverse('get_contests_by_team_ids')
        # Endpoint expects a list of team objects
        data = []
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
    
    def test_get_all_contests_by_organizer(self):
        """Test getting all contests for an organizer"""
        url = reverse('get_all_contests_by_organizer')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response format: {organizer_id: [contests]}
        self.assertIsInstance(response.data, dict)
    
    def test_get_organizer_names_by_contests(self):
        """Test getting organizer names by contest IDs"""
        url = reverse('get_organizer_names_by_contests')
        # Endpoint expects GET
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
    
    def test_get_teams_by_cluster_rank(self):
        """Test getting teams by cluster rank"""
        url = reverse('get_teams_by_cluster_rank')
        data = {
            "clusterid": self.cluster.id
        }
        # Endpoint expects POST with clusterid
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Teams', response.data)
    
    def test_get_teams_by_cluster_rank_missing_params(self):
        """Test getting teams by cluster rank with missing parameters"""
        url = reverse('get_teams_by_cluster_rank')
        data = {}  # Missing clusterid
        response = self.client.post(url, data, format='json')
        
        # Should return 400 Bad Request for missing clusterid
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_teams_by_judge(self):
        """Test getting teams by judge ID"""
        url = reverse('teams_by_judge', args=[self.judge.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response uses capitalized key 'Teams'
        self.assertIn('Teams', response.data)
    
    def test_get_teams_by_judge_invalid(self):
        """Test getting teams for invalid judge ID"""
        url = reverse('teams_by_judge', args=[99999])
        response = self.client.get(url)
        
        # Should handle gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_get_all_clusters_by_judge(self):
        """Test getting all clusters by judge ID"""
        url = reverse('all_clusters_by_judge', args=[self.judge.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response uses capitalized key 'Clusters'
        self.assertIn('Clusters', response.data)
        self.assertGreaterEqual(len(response.data['Clusters']), 1)
    
    def test_get_all_clusters_by_judge_no_clusters(self):
        """Test getting clusters for judge with no clusters"""
        # Create judge with no cluster assignments
        judge_no_clusters = Judge.objects.create(
            first_name="No",
            last_name="Clusters",
            phone_number="1234567890",
            contestid=self.contest.id,
            presentation=True,
            mdo=False,
            journal=True
        )
        
        url = reverse('all_clusters_by_judge', args=[judge_no_clusters.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response uses capitalized key 'Clusters'
        self.assertIn('Clusters', response.data)
        self.assertEqual(len(response.data['Clusters']), 0)
    
    def test_get_all_clusters_by_contest(self):
        """Test getting all clusters by contest ID"""
        url = reverse('all_clusters_by_contest_id', args=[self.contest.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response uses capitalized key 'Clusters'
        self.assertIn('Clusters', response.data)
        self.assertGreaterEqual(len(response.data['Clusters']), 1)
    
    def test_get_all_clusters_by_contest_no_clusters(self):
        """Test getting clusters for contest with no clusters"""
        url = reverse('all_clusters_by_contest_id', args=[self.contest2.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response uses capitalized key 'Clusters'
        self.assertIn('Clusters', response.data)
        # May return empty list or have default clusters
        self.assertIsInstance(response.data['Clusters'], list)
    
    def test_delete_user_role_mapping(self):
        """Test deleting user role mapping"""
        # Create a mapping to delete
        new_user = User.objects.create_user(username="newuser@example.com", password="password")
        mapping = MapUserToRole.objects.create(
            uuid=new_user.id,
            role=2,
            relatedid=self.organizer.id
        )
        
        url = reverse('delete_user_role_mapping', args=[mapping.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify mapping was deleted
        self.assertFalse(MapUserToRole.objects.filter(id=mapping.id).exists())
    
    def test_delete_user_role_mapping_invalid(self):
        """Test deleting invalid user role mapping"""
        url = reverse('delete_user_role_mapping', args=[99999])
        response = self.client.delete(url)
        
        # Should handle gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_get_awards_by_role(self):
        """Test getting awards by role (judge/organizer)"""
        url = reverse('get_awards_by_role', args=['true'])  # isJudge=True
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response is a list, not a dict with 'awards' key
        self.assertIsInstance(response.data, list)
    
    def test_get_awards_by_role_organizer(self):
        """Test getting awards for organizer role"""
        url = reverse('get_awards_by_role', args=['false'])  # isJudge=False
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response is a list, not a dict with 'awards' key
        self.assertIsInstance(response.data, list)

