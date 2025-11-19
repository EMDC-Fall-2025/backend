from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from ..models import Admin, MapUserToRole
from ..serializers import AdminSerializer

class UserAuthTests(APITestCase):

    def setUp(self):
        # Create a test user
        self.user_data = {
            'username': 'testuser',
            'password': 'testpassword',
            'email': 'test@example.com'
        }
        self.user = User.objects.create_user(**self.user_data)

        # Create an Admin object
        self.admin_data = {
            'first_name': 'Test',
            'last_name': 'Admin',
        }
        self.admin = Admin.objects.create(**self.admin_data)

        # Map user to Admin role
        self.mapping = MapUserToRole.objects.create(
            uuid=self.user.id,
            role=1,  # Assuming 1 is the role for Admin
            relatedid=self.admin.id
        )

    def test_login(self):
        url = reverse('login')
        response = self.client.post(url, {
            'username': self.user.username,
            'password': 'testpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Login endpoint returns JsonResponse, parse JSON manually
        response_data = response.json()
        self.assertIn('user', response_data)
        self.assertEqual(response_data['user']['username'], self.user.username)
        self.assertEqual(response_data['role']['user_type'], 1)  # Ensure user role is Admin

    def test_login_invalid_user(self):
        url = reverse('login')
        response = self.client.post(url, {'username': 'invaliduser', 'password': 'wrongpassword'})
        # Login endpoint returns 401 for invalid credentials (not 404)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # Login endpoint returns JsonResponse, parse JSON manually
        response_data = response.json()
        self.assertEqual(response_data['detail'], 'Invalid credentials')

    def test_signup(self):
        url = reverse('signup')
        new_user_data = {
            'username': 'newuser@example.com',  # Must be a valid email
            'password': 'NewPassword123!'
        }
        response = self.client.post(url, new_user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Session authentication doesn't return token, check for user instead
        self.assertIn('user', response.data)

    def test_get_user_by_id(self):
        url = reverse('user_by_id', kwargs={'user_id': self.user.id})
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], self.user.username)

    def test_edit_user(self):
        url = reverse('edit_user')
        self.client.login(username='testuser', password='testpassword')
        response = self.client.post(url, {
            'id': self.user.id,
            'username': 'updateduser@example.com',  # Must be a valid email
            'password': 'updatedpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'updateduser@example.com')

    def test_delete_user(self):
        url = reverse('delete_user_by_id', kwargs={'user_id': self.user.id})
        self.client.login(username='testuser', password='testpassword')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'User deleted successfully.')

    def test_session_verification(self):
        url = reverse('test_token')
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(url)

        # Check if the response data contains the entire string
        self.assertIn(f'passed for {self.user.username}', response.data)


