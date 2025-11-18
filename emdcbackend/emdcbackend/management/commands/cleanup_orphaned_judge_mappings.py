"""
Django management command to clean up orphaned MapContestToJudge entries.

This script finds and removes MapContestToJudge entries where the judge
is not actually assigned to any clusters in that contest.

Usage:
    python manage.py cleanup_orphaned_judge_mappings
    python manage.py cleanup_orphaned_judge_mappings --dry-run  # Preview only
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from emdcbackend.models import MapContestToJudge, MapContestToCluster, MapJudgeToCluster


class Command(BaseCommand):
    help = 'Clean up orphaned MapContestToJudge entries where judges are not in any clusters'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        # Get all contest-judge mappings
        all_mappings = MapContestToJudge.objects.all()
        total_mappings = all_mappings.count()
        
        self.stdout.write(f'Found {total_mappings} total MapContestToJudge entries\n')
        
        orphaned_mappings = []
        
        # Check each mapping
        for mapping in all_mappings:
            contest_id = mapping.contestid
            judge_id = mapping.judgeid
            
            # Get all clusters for this contest
            contest_cluster_ids = MapContestToCluster.objects.filter(
                contestid=contest_id
            ).values_list('clusterid', flat=True).distinct()
            
            if not contest_cluster_ids:
                # Contest has no clusters, so this mapping is orphaned
                orphaned_mappings.append(mapping)
                continue
            
            # Check if judge is assigned to any of those clusters
            judge_in_cluster = MapJudgeToCluster.objects.filter(
                judgeid=judge_id,
                clusterid__in=contest_cluster_ids
            ).exists()
            
            if not judge_in_cluster:
                # Judge is not in any clusters for this contest
                orphaned_mappings.append(mapping)
        
        if not orphaned_mappings:
            self.stdout.write(self.style.SUCCESS('No orphaned mappings found!'))
            return
        
        self.stdout.write(f'\nFound {len(orphaned_mappings)} orphaned mappings:\n')
        
        for mapping in orphaned_mappings:
            self.stdout.write(
                f'  - Judge ID {mapping.judgeid} -> Contest ID {mapping.contestid} '
                f'(Mapping ID: {mapping.id})'
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDRY RUN: Would delete {len(orphaned_mappings)} orphaned mappings'
                )
            )
            return
        
        # Delete orphaned mappings
        with transaction.atomic():
            deleted_count, _ = MapContestToJudge.objects.filter(
                id__in=[m.id for m in orphaned_mappings]
            ).delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully deleted {deleted_count} orphaned MapContestToJudge entries!'
            )
        )

