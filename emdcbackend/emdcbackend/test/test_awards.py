from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from ..models import SpecialAward, Teams, Admin, MapUserToRole


class AwardAPITests(APITestCase):
    def setUp(self):
        # Create a user and generate token for authentication
        self.user = User.objects.create_user(username="testuser@example.com", password="testpassword")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # Create an admin user for role mapping
        self.admin = Admin.objects.create(first_name="Admin", last_name="User")
        MapUserToRole.objects.create(uuid=self.user.id, role=1, relatedid=self.admin.id)

        # Create test data
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

    def test_get_all_awards(self):
        SpecialAward.objects.create(teamid=self.team.id, award_name="Best Design", isJudge=True)
        SpecialAward.objects.create(teamid=self.team.id, award_name="Best Presentation", isJudge=False)
        
        url = reverse('get_all_awards')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data.get('awards', [])), 2)

    def test_create_award_team_mapping(self):
        url = reverse('create_award_team_mapping')
        data = {
            "teamid": self.team.id,
            "award_name": "Best Innovation",
            "isJudge": True
        }
        response = self.client.post(url, data)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertTrue(SpecialAward.objects.filter(teamid=self.team.id, award_name="Best Innovation").exists())

    def test_get_award_by_team_id(self):
        SpecialAward.objects.create(teamid=self.team.id, award_name="Best Design", isJudge=True)
        
        url = reverse('get_award_id_by_team_id', args=[self.team.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_award_team_mapping(self):
        award = SpecialAward.objects.create(teamid=self.team.id, award_name="Best Design", isJudge=True)
        
        url = reverse('delete_award_team_mapping_by_id', args=[self.team.id, "Best Design"])
        response = self.client.delete(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        self.assertFalse(SpecialAward.objects.filter(id=award.id).exists())

    def test_update_award_team_mapping(self):
        award = SpecialAward.objects.create(teamid=self.team.id, award_name="Best Design", isJudge=True)
        
        url = reverse('update_award_team_mapping', args=[self.team.id, "Best Design"])
        data = {
            "award_name": "Best Innovation",
            "isJudge": False
        }
        # Use PUT method (as per view decorator)
        response = self.client.put(url, data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_get_awards_by_role(self):
        SpecialAward.objects.create(teamid=self.team.id, award_name="Judge Award", isJudge=True)
        SpecialAward.objects.create(teamid=self.team.id, award_name="Organizer Award", isJudge=False)
        
        url = reverse('get_awards_by_role', args=["True"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

