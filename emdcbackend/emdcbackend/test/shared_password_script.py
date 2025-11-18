"""
Test script to verify shared password update works correctly
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emdcbackend.settings')
django.setup()

from django.contrib.auth.hashers import check_password, make_password
from emdcbackend.models import RoleSharedPassword

# Test: Set password to "abc"
print("1. Setting password to 'abc'...")
RoleSharedPassword.objects.filter(role=2).delete()
hashed_abc = make_password("abc")
RoleSharedPassword.objects.create(role=2, password_hash=hashed_abc)

# Verify "abc" works
shared = RoleSharedPassword.objects.get(role=2)
print(f"   'abc' matches: {check_password('abc', shared.password_hash)}")
print(f"   'bcd' matches: {check_password('bcd', shared.password_hash)}")

# Test: Change password to "bcd"
print("\n2. Changing password to 'bcd'...")
RoleSharedPassword.objects.filter(role=2).delete()
hashed_bcd = make_password("bcd")
RoleSharedPassword.objects.create(role=2, password_hash=hashed_bcd)

# Verify only "bcd" works now
shared = RoleSharedPassword.objects.get(role=2)
print(f"   'abc' matches: {check_password('abc', shared.password_hash)}")
print(f"   'bcd' matches: {check_password('bcd', shared.password_hash)}")

# Check how many entries exist
count = RoleSharedPassword.objects.filter(role=2).count()
print(f"\n3. Number of entries for role 2: {count}")

if check_password('abc', shared.password_hash):
    print("\n❌ PROBLEM: Old password 'abc' still works!")
else:
    print("\n✅ CORRECT: Old password 'abc' no longer works")

