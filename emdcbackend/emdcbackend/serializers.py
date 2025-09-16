from rest_framework import serializers
from .models import Judge, Organizer, Contest, Coach, MapCoachToTeam, Scoresheet, JudgeClusters, MapContestToJudge, \
    MapContestToOrganizer, MapContestToTeam, MapUserToRole, MapJudgeToCluster, MapContestToCluster, SpecialAward
from .models import Teams, Admin, MapClusterToTeam, MapScoresheetToTeamJudge, Ballot, Votes, MapBallotToVote, MapVoteToAward, MapTeamToVote, MapAwardToContest



class JudgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Judge
        fields = '__all__'  # Or specify the fields you want

class ContestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contest
        fields = '__all__'

class OrganizerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organizer
        fields = '__all__'

class CoachSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coach
        fields = '__all__'

class CoachToTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapCoachToTeam
        fields = '__all__'

class MapContestToOrganizerSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapContestToOrganizer
        fields = '__all__'

class MapContestToTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapContestToTeam
        fields = '__all__'

class MapContestToJudgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapContestToJudge
        fields = '__all__'

class JudgeClustersSerializer(serializers.ModelSerializer):
    class Meta:
        model = JudgeClusters
        fields = '__all__'
        
class ScoresheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scoresheet
        fields = '__all__'

class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = '__all__'

class MapUserToRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapUserToRole
        fields = '__all__'

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teams
        fields = '__all__'

class ClusterToTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapClusterToTeam
        fields = '__all__'

class ClusterToJudgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapJudgeToCluster
        fields = '__all__'

class ClusterToContestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapContestToCluster
        fields = '__all__'

class MapScoreSheetToTeamJudgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapScoresheetToTeamJudge
        fields = '__all__'

class MapContestToClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapContestToCluster
        fields = '__all__'

class SpecialAwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialAward
        fields = '__all__'

class BallotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ballot
        fields = '__all__'


class VotesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Votes
        fields = '__all__'

class MapBallotToVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapBallotToVote
        fields = '__all__'

class MapVoteToAwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapVoteToAward
        fields = '__all__'

class MapTeamToVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapTeamToVote
        fields = '__all__'

class MapAwardToContestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapAwardToContest
        fields = '__all__'

