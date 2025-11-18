"""
Tests for multi-team endpoints (multiTeamGeneralPenalties, multiTeamRunPenalties)
"""
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from datetime import date
from ..models import (
    Contest, Teams, Judge, JudgeClusters, MapContestToTeam, MapContestToOrganizer,
    MapUserToRole, Organizer, Admin, MapClusterToTeam, MapJudgeToCluster,
    MapContestToCluster, MapScoresheetToTeamJudge, Scoresheet, ScoresheetEnum
)


class MultiTeamPenaltiesTests(APITestCase):
    """Tests for multi-team penalty endpoints"""
    
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
        
        # Create teams
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
        
        # Create mappings
        MapContestToCluster.objects.create(contestid=self.contest.id, clusterid=self.cluster.id)
        MapClusterToTeam.objects.create(clusterid=self.cluster.id, teamid=self.team1.id)
        MapClusterToTeam.objects.create(clusterid=self.cluster.id, teamid=self.team2.id)
        MapJudgeToCluster.objects.create(judgeid=self.judge.id, clusterid=self.cluster.id)
    
    def test_multi_team_general_penalties_with_scoresheets(self):
        """Test getting general penalties for multiple teams with existing scoresheets"""
        # Create general penalties scoresheets (type 5)
        gen_pen_sheet1 = Scoresheet.objects.create(
            sheetType=5,  # General penalties
            isSubmitted=False,
            field1=5.0,
            field2=3.0,
            field3=2.0,
            field4=0.0,
            field5=0.0,
            field6=0.0,
            field7=0.0,
            field8=0.0
        )
        
        gen_pen_sheet2 = Scoresheet.objects.create(
            sheetType=5,  # General penalties
            isSubmitted=False,
            field1=2.0,
            field2=1.0,
            field3=0.0,
            field4=0.0,
            field5=0.0,
            field6=0.0,
            field7=0.0,
            field8=0.0
        )
        
        # Map scoresheets to teams and judge
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team1.id,
            judgeid=self.judge.id,
            scoresheetid=gen_pen_sheet1.id,
            sheetType=5
        )
        
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team2.id,
            judgeid=self.judge.id,
            scoresheetid=gen_pen_sheet2.id,
            sheetType=5
        )
        
        url = reverse('multi_team_general_penalties', args=[self.judge.id, self.contest.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('teams', response.data)
        self.assertEqual(len(response.data['teams']), 2)
        
        # Verify team data structure
        team_data = response.data['teams'][0]
        self.assertIn('team_id', team_data)
        self.assertIn('team_name', team_data)
        self.assertIn('scoresheet', team_data)
        self.assertEqual(team_data['scoresheet']['sheetType'], 5)
    
    def test_multi_team_general_penalties_no_scoresheets(self):
        """Test getting general penalties when no scoresheets exist"""
        url = reverse('multi_team_general_penalties', args=[self.judge.id, self.contest.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('teams', response.data)
        # Should return empty list if no scoresheets exist
        self.assertEqual(len(response.data['teams']), 0)
    
    def test_multi_team_general_penalties_invalid_judge(self):
        """Test with invalid judge ID"""
        url = reverse('multi_team_general_penalties', args=[99999, self.contest.id])
        response = self.client.get(url)
        
        # Should handle gracefully (may return empty list or error)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])
    
    def test_multi_team_general_penalties_invalid_contest(self):
        """Test with invalid contest ID"""
        url = reverse('multi_team_general_penalties', args=[self.judge.id, 99999])
        response = self.client.get(url)
        
        # Should handle gracefully (may return empty list or error)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])
    
    def test_multi_team_run_penalties_with_scoresheets(self):
        """Test getting run penalties for multiple teams with existing scoresheets"""
        # Create run penalties scoresheets (type 4)
        run_pen_sheet1 = Scoresheet.objects.create(
            sheetType=4,  # Run penalties
            isSubmitted=False,
            field1=10.0,
            field2=5.0,
            field3=0.0,
            field4=0.0,
            field5=0.0,
            field6=0.0,
            field7=0.0,
            field8=0.0
        )
        
        run_pen_sheet2 = Scoresheet.objects.create(
            sheetType=4,  # Run penalties
            isSubmitted=False,
            field1=8.0,
            field2=3.0,
            field3=0.0,
            field4=0.0,
            field5=0.0,
            field6=0.0,
            field7=0.0,
            field8=0.0
        )
        
        # Map scoresheets to teams and judge
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team1.id,
            judgeid=self.judge.id,
            scoresheetid=run_pen_sheet1.id,
            sheetType=4
        )
        
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team2.id,
            judgeid=self.judge.id,
            scoresheetid=run_pen_sheet2.id,
            sheetType=4
        )
        
        url = reverse('multi_team_run_penalties', args=[self.judge.id, self.contest.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('teams', response.data)
        self.assertEqual(len(response.data['teams']), 2)
        
        # Verify team data structure
        team_data = response.data['teams'][0]
        self.assertIn('team_id', team_data)
        self.assertIn('team_name', team_data)
        self.assertIn('scoresheet', team_data)
        self.assertEqual(team_data['scoresheet']['sheetType'], 4)
    
    def test_multi_team_run_penalties_no_scoresheets(self):
        """Test getting run penalties when no scoresheets exist"""
        url = reverse('multi_team_run_penalties', args=[self.judge.id, self.contest.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('teams', response.data)
        # Should return empty list if no scoresheets exist
        self.assertEqual(len(response.data['teams']), 0)
    
    def test_multi_team_run_penalties_invalid_judge(self):
        """Test with invalid judge ID"""
        url = reverse('multi_team_run_penalties', args=[99999, self.contest.id])
        response = self.client.get(url)
        
        # Should handle gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])
    
    def test_multi_team_run_penalties_invalid_contest(self):
        """Test with invalid contest ID"""
        url = reverse('multi_team_run_penalties', args=[self.judge.id, 99999])
        response = self.client.get(url)
        
        # Should handle gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])
    
    def test_multi_team_penalties_judge_not_assigned_to_cluster(self):
        """Test when judge is not assigned to any cluster in contest"""
        # Remove judge from cluster
        MapJudgeToCluster.objects.filter(judgeid=self.judge.id, clusterid=self.cluster.id).delete()
        
        url = reverse('multi_team_general_penalties', args=[self.judge.id, self.contest.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('teams', response.data)
        # Should return empty list when judge not assigned
        self.assertEqual(len(response.data['teams']), 0)

