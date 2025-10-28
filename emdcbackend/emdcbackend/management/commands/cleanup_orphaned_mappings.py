from django.core.management.base import BaseCommand
from emdcbackend.models import (
    Contest, MapContestToJudge, MapContestToTeam, 
    MapContestToOrganizer, MapContestToCluster
)

class Command(BaseCommand):
    help = 'Clean up orphaned contest mappings (mappings pointing to non-existent contests)'

    def handle(self, *args, **options):
        self.stdout.write('Starting cleanup of orphaned contest mappings...')
        
        # Get all existing contest IDs
        existing_contest_ids = set(Contest.objects.values_list('id', flat=True))
        self.stdout.write(f'Found {len(existing_contest_ids)} existing contests: {sorted(existing_contest_ids)}')
        
        # Clean up MapContestToJudge
        judge_mappings = MapContestToJudge.objects.all()
        orphaned_judge_mappings = judge_mappings.exclude(contestid__in=existing_contest_ids)
        judge_count = orphaned_judge_mappings.count()
        if judge_count > 0:
            self.stdout.write(f'Removing {judge_count} orphaned judge mappings...')
            for mapping in orphaned_judge_mappings:
                self.stdout.write(f'  - Judge {mapping.judgeid} -> Contest {mapping.contestid}')
            orphaned_judge_mappings.delete()
        
        # Clean up MapContestToTeam
        team_mappings = MapContestToTeam.objects.all()
        orphaned_team_mappings = team_mappings.exclude(contestid__in=existing_contest_ids)
        team_count = orphaned_team_mappings.count()
        if team_count > 0:
            self.stdout.write(f'Removing {team_count} orphaned team mappings...')
            for mapping in orphaned_team_mappings:
                self.stdout.write(f'  - Team {mapping.teamid} -> Contest {mapping.contestid}')
            orphaned_team_mappings.delete()
        
        # Clean up MapContestToOrganizer
        organizer_mappings = MapContestToOrganizer.objects.all()
        orphaned_organizer_mappings = organizer_mappings.exclude(contestid__in=existing_contest_ids)
        organizer_count = orphaned_organizer_mappings.count()
        if organizer_count > 0:
            self.stdout.write(f'Removing {organizer_count} orphaned organizer mappings...')
            for mapping in orphaned_organizer_mappings:
                self.stdout.write(f'  - Organizer {mapping.organizerid} -> Contest {mapping.contestid}')
            orphaned_organizer_mappings.delete()
        
        # Clean up MapContestToCluster
        cluster_mappings = MapContestToCluster.objects.all()
        orphaned_cluster_mappings = cluster_mappings.exclude(contestid__in=existing_contest_ids)
        cluster_count = orphaned_cluster_mappings.count()
        if cluster_count > 0:
            self.stdout.write(f'Removing {cluster_count} orphaned cluster mappings...')
            for mapping in orphaned_cluster_mappings:
                self.stdout.write(f'  - Cluster {mapping.clusterid} -> Contest {mapping.contestid}')
            orphaned_cluster_mappings.delete()
        
        total_removed = judge_count + team_count + organizer_count + cluster_count
        
        if total_removed == 0:
            self.stdout.write(self.style.SUCCESS('No orphaned mappings found!'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully removed {total_removed} orphaned mappings'))
        
        self.stdout.write('Cleanup completed!')
