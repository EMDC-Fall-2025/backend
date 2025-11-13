"""
Django management command to create admin accounts.

This is the recommended way to create admin accounts in all environments.

Usage:
    # Interactive mode (prompts for input)
    python manage.py create_first_admin
    
    # Non-interactive mode (provide all details)
    python manage.py create_first_admin --username admin@example.com --password SecurePass123! --first-name Admin --last-name User
"""

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth.models import User
from emdcbackend.models import Admin, MapUserToRole
from emdcbackend.serializers import AdminSerializer


class Command(BaseCommand):
    help = 'Create an admin account (works for first admin or additional admins)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Email address for the admin account',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the admin account',
        )
        parser.add_argument(
            '--first-name',
            type=str,
            default='Admin',
            help='First name of the admin',
        )
        parser.add_argument(
            '--last-name',
            type=str,
            default='User',
            help='Last name of the admin',
        )

    def handle(self, *args, **options):
        # Check if any admins already exist
        admin_count = MapUserToRole.objects.filter(role=MapUserToRole.RoleEnum.ADMIN).count()
        if admin_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Note: {admin_count} admin(s) already exist. Creating additional admin...'
                )
            )

        # Get input interactively if not provided
        username = options.get('username')
        if not username:
            username = input('Email address (username): ').strip()
            if not username:
                self.stdout.write(self.style.ERROR('Username is required.'))
                return

        password = options.get('password')
        if not password:
            password = input('Password: ').strip()
            if not password:
                self.stdout.write(self.style.ERROR('Password is required.'))
                return

        first_name = options.get('first_name', 'Admin')
        last_name = options.get('last_name', 'User')

        # Check if user already exists
        existing_user = User.objects.filter(username__iexact=username).first()
        if existing_user:
            existing_map = MapUserToRole.objects.filter(
                uuid=existing_user.id, role=MapUserToRole.RoleEnum.ADMIN
            ).first()
            if existing_map:
                self.stdout.write(
                    self.style.WARNING(
                        f'Admin already exists for user: {username}'
                    )
                )
                return

        try:
            with transaction.atomic():
                # Create user if doesn't exist
                if not existing_user:
                    user = User.objects.create_user(username=username, password=password)
                    self.stdout.write(self.style.SUCCESS(f'Created user: {username}'))
                else:
                    user = existing_user
                    user.set_password(password)
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f'Updated password for user: {username}'))

                # Create admin
                admin_data = {"first_name": first_name, "last_name": last_name}
                serializer = AdminSerializer(data=admin_data)
                if serializer.is_valid():
                    admin = serializer.save()
                    self.stdout.write(self.style.SUCCESS(f'Created admin: {first_name} {last_name}'))
                else:
                    raise ValidationError(serializer.errors)

                # Create role mapping
                MapUserToRole.objects.get_or_create(
                    uuid=user.id,
                    role=MapUserToRole.RoleEnum.ADMIN,
                    defaults={'relatedid': admin.id}
                )
                self.stdout.write(self.style.SUCCESS('Created admin role mapping'))

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully created admin account!\n'
                    f'  Username: {username}\n'
                    f'  Name: {first_name} {last_name}\n'
                    f'  You can now log in at /api/login/'
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating admin: {str(e)}'))
            raise

