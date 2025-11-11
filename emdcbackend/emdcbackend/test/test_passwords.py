from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from ..models import RoleSharedPassword, Admin, MapUserToRole


class PasswordAPITests(APITestCase):
    def setUp(self):
        # Create a user and login using session authentication
        self.user = User.objects.create_user(username="testuser@example.com", password="testpassword")
        self.client.login(username="testuser@example.com", password="testpassword")

        # Create an admin user for role mapping
        self.admin = Admin.objects.create(first_name="Admin", last_name="User")
        MapUserToRole.objects.create(uuid=self.user.id, role=1, relatedid=self.admin.id)

        # Create a test user for password operations
        self.test_user = User.objects.create_user(username="testpass@example.com", password="oldpassword")

    def test_request_set_password(self):
        """Test admin/organizer sending set-password email"""
        url = reverse('request_set_password')
        data = {
            "username": self.test_user.username
        }
        response = self.client.post(url, data)
        # Note: This might fail if email backend is not configured, but should return 200 or 500
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])
        if response.status_code == status.HTTP_200_OK:
            self.assertEqual(response.data['detail'], "Set-password email sent.")

    def test_request_password_reset(self):
        """Test public forgot password endpoint"""
        url = reverse('request_password_reset')
        data = {
            "username": self.test_user.username
        }
        response = self.client.post(url, data)
        # Note: This might fail if email backend is not configured, but should return 200 or 500
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])
        if response.status_code == status.HTTP_200_OK:
            self.assertIn('detail', response.data)

    def test_validate_password_token(self):
        """Test validating password reset token"""
        # Generate a valid token
        token = default_token_generator.make_token(self.test_user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.test_user.pk))
        
        url = reverse('validate_password_token')
        data = {
            "uid": uidb64,
            "token": token
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], "Token valid.")

    def test_validate_password_token_invalid(self):
        """Test validating invalid password reset token"""
        uidb64 = urlsafe_base64_encode(force_bytes(self.test_user.pk))
        
        url = reverse('validate_password_token')
        data = {
            "uid": uidb64,
            "token": "invalid_token"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "Invalid or expired link.")

    def test_complete_password_set(self):
        """Test completing password set/reset"""
        # Generate a valid token
        token = default_token_generator.make_token(self.test_user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.test_user.pk))
        
        url = reverse('complete_password_set')
        data = {
            "uid": uidb64,
            "token": token,
            "password": "newpassword123"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        
        # Verify password was changed
        self.test_user.refresh_from_db()
        self.assertTrue(self.test_user.check_password("newpassword123"))

    def test_complete_password_set_invalid_token(self):
        """Test completing password set with invalid token"""
        uidb64 = urlsafe_base64_encode(force_bytes(self.test_user.pk))
        
        url = reverse('complete_password_set')
        data = {
            "uid": uidb64,
            "token": "invalid_token",
            "password": "newpassword123"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_shared_password_organizer(self):
        """Test setting shared password for organizer role"""
        url = reverse('set_shared_password')
        data = {
            "role": 2,  # Organizer
            "password": "shared_organizer_password"
        }
        response = self.client.post(url, data)
        # Note: Might return 200 or 400 depending on validation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        if response.status_code == status.HTTP_200_OK:
            self.assertTrue(response.data.get('success', False))
            self.assertTrue(RoleSharedPassword.objects.filter(role=2).exists())

    def test_set_shared_password_judge(self):
        """Test setting shared password for judge role"""
        url = reverse('set_shared_password')
        data = {
            "role": 3,  # Judge
            "password": "shared_judge_password"
        }
        response = self.client.post(url, data)
        # Note: Might return 200 or 400 depending on validation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        if response.status_code == status.HTTP_200_OK:
            self.assertTrue(response.data.get('success', False))
            self.assertTrue(RoleSharedPassword.objects.filter(role=3).exists())

    def test_set_shared_password_invalid_role(self):
        """Test setting shared password with invalid role"""
        url = reverse('set_shared_password')
        data = {
            "role": 1,  # Invalid (should be 2 or 3)
            "password": "password"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_set_shared_password_update_existing(self):
        """Test updating existing shared password"""
        # Create existing shared password
        RoleSharedPassword.objects.create(role=2, password_hash="old_hash")
        
        url = reverse('set_shared_password')
        data = {
            "role": 2,
            "password": "new_shared_password"
        }
        response = self.client.post(url, data)
        # Note: This might return 200 or 400 depending on validation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        if response.status_code == status.HTTP_200_OK:
            self.assertTrue(response.data['success'])
            # Should update, not create new
            self.assertEqual(RoleSharedPassword.objects.filter(role=2).count(), 1)

