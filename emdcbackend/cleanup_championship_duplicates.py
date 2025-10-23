#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emdcbackend.settings')
django.setup()

from emdcbackend.models import Teams, MapScoresheetToTeamJudge, Scoresheet, ScoresheetEnum

def cleanup_championship_duplicates():
    """Clean up duplicate championship scoresheet mappings."""
    print("Starting championship duplicate cleanup...")
    
    # Get all championship teams
    championship_teams = Teams.objects.filter(advanced_to_championship=True)
    print(f"Found {championship_teams.count()} championship teams")
    
    total_duplicates_removed = 0
    
    for team in championship_teams:
        print(f"\nProcessing team: {team.team_name}")
        
        # Get all mappings for this team
        mappings = MapScoresheetToTeamJudge.objects.filter(teamid=team.id)
        
        # Filter for championship scoresheets
        championship_mappings = []
        for mapping in mappings:
            try:
                sheet = Scoresheet.objects.get(id=mapping.scoresheetid)
                if sheet.sheetType == ScoresheetEnum.CHAMPIONSHIP:
                    championship_mappings.append(mapping)
            except Scoresheet.DoesNotExist:
                continue
        
        print(f"Found {len(championship_mappings)} championship mappings")
        
        if len(championship_mappings) <= 1:
            print("No duplicates found for this team")
            continue
        
        # Group by unique scores (field1, field2, field3)
        unique_scoresheets = {}
        for mapping in championship_mappings:
            sheet = Scoresheet.objects.get(id=mapping.scoresheetid)
            key = (sheet.field1, sheet.field2, sheet.field3)
            
            if key not in unique_scoresheets:
                unique_scoresheets[key] = mapping
            else:
                # Keep the submitted one, or the most recent one
                existing_mapping = unique_scoresheets[key]
                existing_sheet = Scoresheet.objects.get(id=existing_mapping.scoresheetid)
                
                if sheet.isSubmitted and not existing_sheet.isSubmitted:
                    # Replace with submitted version
                    unique_scoresheets[key] = mapping
                elif sheet.isSubmitted == existing_sheet.isSubmitted:
                    # Both same submission status, keep the one with higher ID (more recent)
                    if sheet.id > existing_sheet.id:
                        unique_scoresheets[key] = mapping
        
        print(f"Unique scoresheets found: {len(unique_scoresheets)}")
        
        # Find duplicates to delete
        duplicates = []
        for mapping in championship_mappings:
            if mapping not in unique_scoresheets.values():
                duplicates.append(mapping)
        
        print(f"Deleting {len(duplicates)} duplicate mappings")
        
        # Delete duplicates
        for mapping in duplicates:
            mapping.delete()
            total_duplicates_removed += 1
        
        print(f"Cleanup complete for {team.team_name}")
    
    print(f"\nTotal duplicates removed: {total_duplicates_removed}")
    print("Championship duplicate cleanup completed!")

if __name__ == "__main__":
    cleanup_championship_duplicates()
