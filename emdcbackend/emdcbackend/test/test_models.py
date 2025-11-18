from django.test import TestCase
from datetime import date
from ..models import (
    Contest,
    MapContestToJudge,
    MapContestToTeam,
    MapContestToOrganizer,
    MapContestToCluster,
    Judge,
    MapJudgeToCluster,
    JudgeClusters,
    MapClusterToTeam,
    Teams,
    MapUserToRole,
    Coach,
    Admin,
    MapCoachToTeam,
    Organizer,
    Scoresheet,
    ScoresheetEnum,
    MapScoresheetToTeamJudge,
    SpecialAward,
    Ballot,
    Votes,
    MapBallotToVote,
    MapVoteToAward,
    MapTeamToVote,
    MapAwardToContest,
    RoleSharedPassword,
)

class ContestModelTest(TestCase):
    def test_contest_creation(self):
        contest = Contest.objects.create(name="Math Contest", date=date.today(), is_open=True, is_tabulated=False)
        self.assertEqual(contest.name, "Math Contest")
        self.assertTrue(contest.is_open)
        self.assertFalse(contest.is_tabulated)

class MapContestToJudgeModelTest(TestCase):
    def test_map_contest_to_judge_creation(self):
        mapping = MapContestToJudge.objects.create(contestid=1, judgeid=2)
        self.assertEqual(mapping.contestid, 1)
        self.assertEqual(mapping.judgeid, 2)

class MapContestToTeamModelTest(TestCase):
    def test_map_contest_to_team_creation(self):
        mapping = MapContestToTeam.objects.create(contestid=1, teamid=3)
        self.assertEqual(mapping.contestid, 1)
        self.assertEqual(mapping.teamid, 3)

class MapContestToOrganizerModelTest(TestCase):
    def test_map_contest_to_organizer_creation(self):
        mapping = MapContestToOrganizer.objects.create(contestid=1, organizerid=4)
        self.assertEqual(mapping.contestid, 1)
        self.assertEqual(mapping.organizerid, 4)

class JudgeModelTest(TestCase):
    def test_judge_creation(self):
        judge = Judge.objects.create(
            first_name="Alice", 
            last_name="Brown", 
            phone_number="1234567890",
            contestid=1, 
            presentation=True, 
            mdo=False, 
            journal=True
        )
        self.assertEqual(judge.first_name, "Alice")
        self.assertEqual(judge.last_name, "Brown")
        self.assertEqual(judge.contestid, 1)
        self.assertTrue(judge.presentation)

class MapJudgeToClusterModelTest(TestCase):
    def test_map_judge_to_cluster_creation(self):
        mapping = MapJudgeToCluster.objects.create(judgeid=5, clusterid=1)
        self.assertEqual(mapping.judgeid, 5)
        self.assertEqual(mapping.clusterid, 1)

class JudgeClustersModelTest(TestCase):
    def test_judge_cluster_creation(self):
        cluster = JudgeClusters.objects.create(cluster_name="Cluster A")
        self.assertEqual(cluster.cluster_name, "Cluster A")

class MapClusterToTeamModelTest(TestCase):
    def test_map_cluster_to_team_creation(self):
        mapping = MapClusterToTeam.objects.create(clusterid=1, teamid=2)
        self.assertEqual(mapping.clusterid, 1)
        self.assertEqual(mapping.teamid, 2)

class TeamsModelTest(TestCase):
    def test_team_creation(self):
        team = Teams.objects.create(
            team_name="Team Alpha",
            journal_score=95.0,
            presentation_score=90.0,
            machinedesign_score=85.0,
            penalties_score=0.0,
            redesign_score=0.0,
            total_score=270.0,
            championship_score=0.0
        )
        self.assertEqual(team.team_name, "Team Alpha")
        self.assertEqual(team.journal_score, 95.0)

class MapUserToRoleModelTest(TestCase):
    def test_map_user_to_role_creation(self):
        mapping = MapUserToRole.objects.create(role=1, uuid=1, relatedid=2)
        self.assertEqual(mapping.role, 1)
        self.assertEqual(mapping.uuid, 1)

class CoachModelTest(TestCase):
    def test_coach_creation(self):
        coach = Coach.objects.create(first_name="John", last_name="Doe")
        self.assertEqual(coach.first_name, "John")

class AdminModelTest(TestCase):
    def test_admin_creation(self):
        admin = Admin.objects.create(first_name="Sara", last_name="Connor")
        self.assertEqual(admin.first_name, "Sara")

class MapCoachToTeamModelTest(TestCase):
    def test_map_coach_to_team_creation(self):
        mapping = MapCoachToTeam.objects.create(teamid=1, coachid=2)
        self.assertEqual(mapping.teamid, 1)

class OrganizerModelTest(TestCase):
    def test_organizer_creation(self):
        organizer = Organizer.objects.create(first_name="Alice", last_name="Johnson")
        self.assertEqual(organizer.first_name, "Alice")

class ScoresheetModelTest(TestCase):
    def test_scoresheet_creation(self):
        scoresheet = Scoresheet.objects.create(
            sheetType=ScoresheetEnum.PRESENTATION,
            isSubmitted=False,
            field1=1,
            field2=2,
            field3=3,
            field4=4,
            field5=5,
            field6=6,
            field7=7,
            field8=8,
        )
        self.assertEqual(scoresheet.sheetType, ScoresheetEnum.PRESENTATION)

class MapScoresheetToTeamJudgeModelTest(TestCase):
    def test_map_scoresheet_to_team_judge_creation(self):
        mapping = MapScoresheetToTeamJudge.objects.create(
            teamid=1, 
            judgeid=1, 
            scoresheetid=1,
            sheetType=ScoresheetEnum.PRESENTATION
        )
        self.assertEqual(mapping.teamid, 1)
        self.assertEqual(mapping.judgeid, 1)

class MapContestToClusterModelTest(TestCase):
    def test_map_contest_to_cluster_creation(self):
        mapping = MapContestToCluster.objects.create(contestid=1, clusterid=2)
        self.assertEqual(mapping.contestid, 1)
        self.assertEqual(mapping.clusterid, 2)

class SpecialAwardModelTest(TestCase):
    def test_special_award_creation(self):
        award = SpecialAward.objects.create(teamid=1, award_name="Best Design", isJudge=True)
        self.assertEqual(award.teamid, 1)
        self.assertEqual(award.award_name, "Best Design")
        self.assertTrue(award.isJudge)

class BallotModelTest(TestCase):
    def test_ballot_creation(self):
        ballot = Ballot.objects.create(contestid=1, isSubmitted=False)
        self.assertEqual(ballot.contestid, 1)
        self.assertFalse(ballot.isSubmitted)

class VotesModelTest(TestCase):
    def test_votes_creation(self):
        vote = Votes.objects.create(votedteamid=1)
        self.assertEqual(vote.votedteamid, 1)

class MapBallotToVoteModelTest(TestCase):
    def test_map_ballot_to_vote_creation(self):
        mapping = MapBallotToVote.objects.create(ballotid=1, voteid=2)
        self.assertEqual(mapping.ballotid, 1)
        self.assertEqual(mapping.voteid, 2)

class MapVoteToAwardModelTest(TestCase):
    def test_map_vote_to_award_creation(self):
        mapping = MapVoteToAward.objects.create(awardid=1, voteid=2)
        self.assertEqual(mapping.awardid, 1)
        self.assertEqual(mapping.voteid, 2)

class MapTeamToVoteModelTest(TestCase):
    def test_map_team_to_vote_creation(self):
        mapping = MapTeamToVote.objects.create(teamid=1, voteid=2)
        self.assertEqual(mapping.teamid, 1)
        self.assertEqual(mapping.voteid, 2)

class MapAwardToContestModelTest(TestCase):
    def test_map_award_to_contest_creation(self):
        mapping = MapAwardToContest.objects.create(contestid=1, awardid=2)
        self.assertEqual(mapping.contestid, 1)
        self.assertEqual(mapping.awardid, 2)

class RoleSharedPasswordModelTest(TestCase):
    def test_role_shared_password_creation(self):
        password = RoleSharedPassword.objects.create(role=2, password_hash="hashed_password")
        self.assertEqual(password.role, 2)
        self.assertEqual(password.password_hash, "hashed_password")
