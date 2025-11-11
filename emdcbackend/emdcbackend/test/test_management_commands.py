"""
Tests for Django management commands
"""
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from datetime import date
from ..models import (
    Contest, MapContestToJudge, MapContestToTeam,
    MapContestToOrganizer, MapContestToCluster, Judge, Teams, Organizer, JudgeClusters
)


class CleanupOrphanedMappingsCommandTests(TestCase):
    """Test the cleanup_orphaned_mappings management command"""
    
    def setUp(self):
        """Set up test data"""
        self.contest = Contest.objects.create(
            name="Test Contest",
            date=date.today(),
            is_open=True,
            is_tabulated=False
        )
        self.judge = Judge.objects.create(
            first_name="Test",
            last_name="Judge",
            phone_number="1234567890",
            contestid=self.contest.id,
            presentation=True
        )
        self.team = Teams.objects.create(
            team_name="Test Team",
            journal_score=90.0,
            presentation_score=85.0,
            machinedesign_score=80.0,
            penalties_score=0.0,
            redesign_score=0.0,
            total_score=255.0,
            championship_score=0.0
        )
        self.organizer = Organizer.objects.create(first_name="Test", last_name="Organizer")
        self.cluster = JudgeClusters.objects.create(cluster_name="Test Cluster")
    
    def test_cleanup_with_no_orphaned_mappings(self):
        """Test cleanup when there are no orphaned mappings"""
        # Create valid mappings
        MapContestToJudge.objects.create(contestid=self.contest.id, judgeid=self.judge.id)
        MapContestToTeam.objects.create(contestid=self.contest.id, teamid=self.team.id)
        MapContestToOrganizer.objects.create(contestid=self.contest.id, organizerid=self.organizer.id)
        MapContestToCluster.objects.create(contestid=self.contest.id, clusterid=self.cluster.id)
        
        out = StringIO()
        call_command('cleanup_orphaned_mappings', stdout=out)
        output = out.getvalue()
        
        # Should report no orphaned mappings
        self.assertIn('No orphaned mappings found', output)
        
        # All mappings should still exist
        self.assertTrue(MapContestToJudge.objects.filter(contestid=self.contest.id).exists())
        self.assertTrue(MapContestToTeam.objects.filter(contestid=self.contest.id).exists())
    
    def test_cleanup_with_orphaned_mappings(self):
        """Test cleanup when there are orphaned mappings"""
        # Create valid mapping
        MapContestToJudge.objects.create(contestid=self.contest.id, judgeid=self.judge.id)
        
        # Create orphaned mappings (pointing to non-existent contest)
        orphaned_judge_mapping = MapContestToJudge.objects.create(contestid=99999, judgeid=self.judge.id)
        orphaned_team_mapping = MapContestToTeam.objects.create(contestid=99999, teamid=self.team.id)
        orphaned_organizer_mapping = MapContestToOrganizer.objects.create(contestid=99999, organizerid=self.organizer.id)
        orphaned_cluster_mapping = MapContestToCluster.objects.create(contestid=99999, clusterid=self.cluster.id)
        
        out = StringIO()
        call_command('cleanup_orphaned_mappings', stdout=out)
        output = out.getvalue()
        
        # Should report cleanup
        self.assertIn('Successfully removed', output)
        
        # Orphaned mappings should be deleted
        self.assertFalse(MapContestToJudge.objects.filter(id=orphaned_judge_mapping.id).exists())
        self.assertFalse(MapContestToTeam.objects.filter(id=orphaned_team_mapping.id).exists())
        self.assertFalse(MapContestToOrganizer.objects.filter(id=orphaned_organizer_mapping.id).exists())
        self.assertFalse(MapContestToCluster.objects.filter(id=orphaned_cluster_mapping.id).exists())
        
        # Valid mapping should still exist
        self.assertTrue(MapContestToJudge.objects.filter(contestid=self.contest.id).exists())
    
    def test_cleanup_with_deleted_contest(self):
        """Test cleanup when contest is deleted"""
        # Create mappings
        valid_mapping = MapContestToJudge.objects.create(contestid=self.contest.id, judgeid=self.judge.id)
        
        # Delete the contest
        self.contest.delete()
        
        out = StringIO()
        call_command('cleanup_orphaned_mappings', stdout=out)
        output = out.getvalue()
        
        # Should clean up mappings for deleted contest
        self.assertIn('Successfully removed', output)
        self.assertFalse(MapContestToJudge.objects.filter(id=valid_mapping.id).exists())

