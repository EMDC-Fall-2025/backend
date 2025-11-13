#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, 'emdcbackend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emdcbackend.settings')
django.setup()

from emdcbackend.models import Judge, MapUserToRole
from django.contrib.auth.models import User
from emdcbackend.views.Maps.MapUserToRole import create_user_role_map

print("Fixing missing MapUserToRole entries for judges...")

judges = Judge.objects.all()
fixed_count = 0

for judge in judges:
    # Check if judge already has a MapUserToRole entry
    existing_mapping = MapUserToRole.objects.filter(role=3, relatedid=judge.id).first()

    if existing_mapping:
        print(f'✅ Judge {judge.id} ({judge.first_name} {judge.last_name}) already has MapUserToRole entry')
        continue

    print(f'❌ Judge {judge.id} ({judge.first_name} {judge.last_name}) is missing MapUserToRole entry')

    # Try to find if there's already a user with this judge's name/email pattern
    # For now, we'll create a new user for each judge missing the mapping
    # In a real scenario, you'd want to match existing users or get proper credentials

    # Create a simple username based on judge name
    base_username = f"{judge.first_name.lower()}.{judge.last_name.lower()}"

    # Ensure unique username
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    # Create user with a default password (should be changed later)
    try:
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",  # Placeholder email
            password="changeme123!",  # Default password - should be changed
            first_name=judge.first_name,
            last_name=judge.last_name
        )

        # Create the MapUserToRole entry
        result = create_user_role_map({
            "uuid": user.id,
            "role": 3,  # JUDGE role
            "relatedid": judge.id
        })

        if result:
            print(f'✅ Created MapUserToRole entry for Judge {judge.id} with user {user.username}')
            fixed_count += 1
        else:
            print(f'❌ Failed to create MapUserToRole entry for Judge {judge.id}')

    except Exception as e:
        print(f'❌ Error creating user/role mapping for Judge {judge.id}: {e}')

print(f"\nDone! Fixed {fixed_count} judges with missing MapUserToRole entries.")
print("⚠️  IMPORTANT: The created users have default password 'changeme123!' - please change these passwords!")
