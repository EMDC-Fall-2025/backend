#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, 'emdcbackend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emdcbackend.settings')
django.setup()

from emdcbackend.models import MapUserToRole, Admin, Organizer, Judge, Coach
from django.contrib.auth.models import User as DjangoUser
from django.db import transaction

print("🔧 Fixing Role Mapping Issues")
print("=" * 50)

issues_fixed = 0

# 1. Remove MapUserToRole entries for non-existent users
print("\n1️⃣ Removing MapUserToRole entries for non-existent users...")
orphaned_mappings = MapUserToRole.objects.exclude(uuid__in=DjangoUser.objects.values_list('id', flat=True))
orphaned_count = orphaned_mappings.count()

if orphaned_count > 0:
    print(f"   Found {orphaned_count} orphaned MapUserToRole entries")
    orphaned_mappings.delete()
    print(f"   ✅ Deleted {orphaned_count} orphaned mappings")
    issues_fixed += orphaned_count
else:
    print("   ✅ No orphaned mappings found")

# 2. Create MapUserToRole entries for orphaned role entities
print("\n2️⃣ Creating MapUserToRole entries for orphaned entities...")

# Handle orphaned admins
orphaned_admins = Admin.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=1).values_list('relatedid', flat=True)
)

for admin in orphaned_admins:
    print(f"   Found orphaned admin: {admin.first_name} {admin.last_name} (ID: {admin.id})")

    # Create a Django user for this admin
    username = f"admin_{admin.id}"
    counter = 1
    while DjangoUser.objects.filter(username=username).exists():
        username = f"admin_{admin.id}_{counter}"
        counter += 1

    user = DjangoUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="changeme123!",
        first_name=admin.first_name,
        last_name=admin.last_name
    )

    # Create the role mapping
    MapUserToRole.objects.create(
        uuid=user.id,
        role=1,  # Admin
        relatedid=admin.id
    )

    print(f"   ✅ Created user '{username}' and role mapping for admin {admin.id}")
    issues_fixed += 1

# Handle orphaned coaches
orphaned_coaches = Coach.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=4).values_list('relatedid', flat=True)
)

for coach in orphaned_coaches:
    print(f"   Found orphaned coach: {coach.first_name} {coach.last_name} (ID: {coach.id})")

    # Create a Django user for this coach
    username = f"coach_{coach.id}"
    counter = 1
    while DjangoUser.objects.filter(username=username).exists():
        username = f"coach_{coach.id}_{counter}"
        counter += 1

    user = DjangoUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="changeme123!",
        first_name=coach.first_name,
        last_name=coach.last_name
    )

    # Create the role mapping
    MapUserToRole.objects.create(
        uuid=user.id,
        role=4,  # Coach
        relatedid=coach.id
    )

    print(f"   ✅ Created user '{username}' and role mapping for coach {coach.id}")
    issues_fixed += 1

# Check for orphaned organizers and judges (these might be expected to not have mappings if they're not active)
orphaned_organizers = Organizer.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=2).values_list('relatedid', flat=True)
)

orphaned_judges = Judge.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=3).values_list('relatedid', flat=True)
)

if orphaned_organizers.exists():
    print(f"\n⚠️  Note: {orphaned_organizers.count()} organizers don't have user mappings (this may be normal)")

if orphaned_judges.exists():
    print(f"\n⚠️  Note: {orphaned_judges.count()} judges don't have user mappings (this may be normal)")

# 3. Check for duplicate role mappings (same user, same role)
print("\n3️⃣ Checking for duplicate role mappings...")
from django.db.models import Count
duplicates = MapUserToRole.objects.values('uuid', 'role').annotate(count=Count('id')).filter(count__gt=1)

if duplicates.exists():
    print(f"   Found {duplicates.count()} duplicate role mappings")
    # Remove duplicates, keeping the first one
    for dup in duplicates:
        mappings = MapUserToRole.objects.filter(uuid=dup['uuid'], role=dup['role']).order_by('id')
        to_delete = mappings[1:]  # Keep the first, delete the rest
        deleted_count = to_delete.delete()[0]
        if deleted_count > 0:
            print(f"   ✅ Removed {deleted_count} duplicate mappings for user {dup['uuid']}, role {dup['role']}")
            issues_fixed += deleted_count
else:
    print("   ✅ No duplicate role mappings found")

print("\n" + "=" * 50)
print("📋 FIX SUMMARY")
print(f"✅ Fixed {issues_fixed} role mapping issues")

if orphaned_admins.exists() or orphaned_coaches.exists():
    print("\n⚠️  IMPORTANT: Created users have default password 'changeme123!' - please change these passwords!")
    created_users = []
    if orphaned_admins.exists():
        created_users.extend([f"admin_{admin.id}" for admin in orphaned_admins])
    if orphaned_coaches.exists():
        created_users.extend([f"coach_{coach.id}" for coach in orphaned_coaches])
    print(f"   Created users: {', '.join(created_users)}")

print("\n🎯 Role mapping integrity check complete!")
