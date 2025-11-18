#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emdcbackend.settings')
django.setup()

from emdcbackend.models import Judge, MapUserToRole

print("Checking judges for MapUserToRole entries...")
judges = Judge.objects.all()
for judge in judges:
    mapping = MapUserToRole.objects.filter(role=3, relatedid=judge.id).first()
    if not mapping:
        print(f'❌ Judge {judge.id} ({judge.first_name} {judge.last_name}) is missing MapUserToRole entry')
    else:
        print(f'✅ Judge {judge.id} has MapUserToRole entry with user {mapping.uuid}')

print("\nDone!")
