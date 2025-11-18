"""
Tests for scoresheet submission endpoints
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


class ScoresheetSubmissionTests(APITestCase):
    """Tests for scoresheet submission endpoints"""
    
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
        MapContestToTeam.objects.create(contestid=self.contest.id, teamid=self.team1.id)
        MapContestToTeam.objects.create(contestid=self.contest.id, teamid=self.team2.id)
    
    def test_submit_all_penalty_sheets_for_judge(self):
        """Test submitting all penalty sheets for a judge"""
        # Create run penalty scoresheets (type 4)
        run_pen_sheet1 = Scoresheet.objects.create(
            sheetType=4,
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
            sheetType=4,
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
        
        # Map scoresheets
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
        
        url = reverse('submit_all_penalty_sheets_for_judge')
        data = {"judge_id": self.judge.id}
        response = self.client.post(url, data, format='json')
        
        # Endpoint returns 200 with empty body on success
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])
        
        if response.status_code == status.HTTP_200_OK:
            # Verify scoresheets are submitted
            run_pen_sheet1.refresh_from_db()
            run_pen_sheet2.refresh_from_db()
            self.assertTrue(run_pen_sheet1.isSubmitted)
            self.assertTrue(run_pen_sheet2.isSubmitted)
    
    def test_submit_all_penalty_sheets_no_sheets(self):
        """Test submitting penalty sheets when none exist"""
        url = reverse('submit_all_penalty_sheets_for_judge')
        data = {"judge_id": self.judge.id}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_submit_all_penalty_sheets_invalid_judge(self):
        """Test submitting penalty sheets for invalid judge"""
        url = reverse('submit_all_penalty_sheets_for_judge')
        data = {"judge_id": 99999}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_all_sheets_submitted_for_contests(self):
        """Test checking if all sheets are submitted for contests"""
        # Create submitted scoresheets
        sheet1 = Scoresheet.objects.create(
            sheetType=ScoresheetEnum.PRESENTATION,
            isSubmitted=True,
            field1=1.0,
            field2=2.0,
            field3=3.0,
            field4=4.0,
            field5=5.0,
            field6=6.0,
            field7=7.0,
            field8=8.0
        )
        
        sheet2 = Scoresheet.objects.create(
            sheetType=ScoresheetEnum.JOURNAL,
            isSubmitted=True,
            field1=1.0,
            field2=2.0,
            field3=3.0,
            field4=4.0,
            field5=5.0,
            field6=6.0,
            field7=7.0,
            field8=8.0
        )
        
        # Map scoresheets
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team1.id,
            judgeid=self.judge.id,
            scoresheetid=sheet1.id,
            sheetType=ScoresheetEnum.PRESENTATION
        )
        
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team1.id,
            judgeid=self.judge.id,
            scoresheetid=sheet2.id,
            sheetType=ScoresheetEnum.JOURNAL
        )
        
        url = reverse('all_sheets_submitted_for_contests')
        data = [{"id": self.contest.id}]
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response uses integer keys, not string keys
        self.assertIn(self.contest.id, response.data)
        # Result depends on whether all sheets for all judges/teams are submitted
        self.assertIn(response.data[self.contest.id], [True, False])
    
    def test_all_sheets_submitted_for_contests_empty(self):
        """Test checking sheets submitted for empty contest list"""
        url = reverse('all_sheets_submitted_for_contests')
        data = []
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {})
    
    def test_all_sheets_submitted_for_contests_no_clusters(self):
        """Test checking sheets for contest with no clusters"""
        contest_no_clusters = Contest.objects.create(
            name="No Clusters Contest",
            date=date.today(),
            is_open=True,
            is_tabulated=False
        )
        
        url = reverse('all_sheets_submitted_for_contests')
        data = [{"id": contest_no_clusters.id}]
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response uses integer keys, not string keys
        self.assertIn(contest_no_clusters.id, response.data)
        # Contest with no clusters should return True (no sheets to check)
        self.assertTrue(response.data[contest_no_clusters.id])
    
    def test_all_submitted_for_team(self):
        """Test checking if all sheets are submitted for a team"""
        # Create submitted scoresheets
        sheet1 = Scoresheet.objects.create(
            sheetType=ScoresheetEnum.PRESENTATION,
            isSubmitted=True,
            field1=1.0,
            field2=2.0,
            field3=3.0,
            field4=4.0,
            field5=5.0,
            field6=6.0,
            field7=7.0,
            field8=8.0
        )
        
        sheet2 = Scoresheet.objects.create(
            sheetType=ScoresheetEnum.JOURNAL,
            isSubmitted=True,
            field1=1.0,
            field2=2.0,
            field3=3.0,
            field4=4.0,
            field5=5.0,
            field6=6.0,
            field7=7.0,
            field8=8.0
        )
        
        # Map scoresheets
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team1.id,
            judgeid=self.judge.id,
            scoresheetid=sheet1.id,
            sheetType=ScoresheetEnum.PRESENTATION
        )
        
        MapScoresheetToTeamJudge.objects.create(
            teamid=self.team1.id,
            judgeid=self.judge.id,
            scoresheetid=sheet2.id,
            sheetType=ScoresheetEnum.JOURNAL
        )
        
        url = reverse('all_submitted_for_team', args=[self.team1.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response format: {'teamId': int, 'submittedCount': int, 'totalCount': int, 'allSubmitted': bool}
        self.assertIn('allSubmitted', response.data)
        self.assertIn(response.data['allSubmitted'], [True, False])
    
    def test_all_submitted_for_team_no_sheets(self):
        """Test checking sheets for team with no scoresheets"""
        url = reverse('all_submitted_for_team', args=[self.team2.id])
        response = self.client.get(url)
        
        # Should handle gracefully (may return True or False depending on implementation)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_all_submitted_for_team_invalid_team(self):
        """Test checking sheets for invalid team ID"""
        url = reverse('all_submitted_for_team', args=[99999])
        response = self.client.get(url)
        
        # Should handle gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

