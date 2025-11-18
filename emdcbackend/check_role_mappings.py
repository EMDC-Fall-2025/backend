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

print("🔍 Comprehensive Role Mapping Analysis")
print("=" * 50)

# Check all MapUserToRole entries
mappings = MapUserToRole.objects.all().order_by('uuid', 'role')
print(f"\n📊 Total MapUserToRole entries: {mappings.count()}")

# Group by user
user_groups = {}
for mapping in mappings:
    if mapping.uuid not in user_groups:
        user_groups[mapping.uuid] = []
    user_groups[mapping.uuid].append(mapping)

print(f"👥 Unique users with roles: {len(user_groups)}")

# Check for issues
issues_found = []

print("\n🔍 Checking for issues...")

for user_id, user_mappings in user_groups.items():
    try:
        django_user = DjangoUser.objects.get(id=user_id)
        user_name = f"{django_user.first_name} {django_user.last_name}".strip() or django_user.username
    except DjangoUser.DoesNotExist:
        issues_found.append(f"❌ User {user_id} in MapUserToRole doesn't exist in Django User table")
        continue

    # Check if user has multiple roles
    if len(user_mappings) > 1:
        roles = [m.role for m in user_mappings]
        issues_found.append(f"⚠️  User {user_id} ({user_name}) has multiple roles: {roles}")

    # Check if the related entity exists
    for mapping in user_mappings:
        try:
            if mapping.role == 1:  # Admin
                Admin.objects.get(id=mapping.relatedid)
            elif mapping.role == 2:  # Organizer
                Organizer.objects.get(id=mapping.relatedid)
            elif mapping.role == 3:  # Judge
                Judge.objects.get(id=mapping.relatedid)
            elif mapping.role == 4:  # Coach
                Coach.objects.get(id=mapping.relatedid)
        except Exception as e:
            role_names = {1: 'Admin', 2: 'Organizer', 3: 'Judge', 4: 'Coach'}
            role_name = role_names.get(mapping.role, f'Role {mapping.role}')
            issues_found.append(f"❌ {role_name} {mapping.relatedid} referenced by user {user_id} ({user_name}) doesn't exist")

# Check for orphaned entities (entities without user mappings)
print("\n🔍 Checking for orphaned entities...")

admins_without_users = Admin.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=1).values_list('relatedid', flat=True)
)
if admins_without_users.exists():
    issues_found.append(f"❌ {admins_without_users.count()} Admin entities without user mappings")

organizers_without_users = Organizer.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=2).values_list('relatedid', flat=True)
)
if organizers_without_users.exists():
    issues_found.append(f"❌ {organizers_without_users.count()} Organizer entities without user mappings")

judges_without_users = Judge.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=3).values_list('relatedid', flat=True)
)
if judges_without_users.exists():
    issues_found.append(f"❌ {judges_without_users.count()} Judge entities without user mappings")

coaches_without_users = Coach.objects.exclude(
    id__in=MapUserToRole.objects.filter(role=4).values_list('relatedid', flat=True)
)
if coaches_without_users.exists():
    issues_found.append(f"❌ {coaches_without_users.count()} Coach entities without user mappings")

# Summary
print("\n" + "=" * 50)
print("📋 SUMMARY")

if issues_found:
    print(f"❌ Found {len(issues_found)} issues:")
    for issue in issues_found:
        print(f"   {issue}")
else:
    print("✅ No issues found! All role mappings appear to be correct.")

print("\n📈 Role Distribution:")
role_counts = {1: 0, 2: 0, 3: 0, 4: 0}
for mapping in mappings:
    role_counts[mapping.role] = role_counts.get(mapping.role, 0) + 1

role_names = {1: 'Admins', 2: 'Organizers', 3: 'Judges', 4: 'Coaches'}
for role_id, count in role_counts.items():
    print(f"   {role_names.get(role_id, f'Role {role_id}')}: {count}")

print("\nDone! 🎯")
