from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from .Maps.MapScoreSheet import delete_score_sheet_mapping
from ..models import Scoresheet, Teams, Judge, MapClusterToTeam, MapScoresheetToTeamJudge, MapJudgeToCluster, ScoresheetEnum, Contest, MapContestToTeam
from ..serializers import ScoresheetSerializer, MapScoreSheetToTeamJudgeSerializer

@api_view(["GET"])
def scores_by_id(request, scores_id):
    scores = get_object_or_404(Scoresheet, id=scores_id)
    serializer = ScoresheetSerializer(instance=scores)
    return Response({"ScoreSheet": serializer.data}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_score_sheet(request):
    map_data = request.data
    result = create_score_sheet_helper(map_data)
    if "errors" in result:
        return Response(result["errors"], status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def edit_score_sheet(request):
    try:
        scores = get_object_or_404(Scoresheet, id=request.data["id"])
        scores.sheetType = request.data["sheetType"]
        scores.isSubmitted = request.data["isSubmitted"]
        
        if scores.sheetType == ScoresheetEnum.OTHERPENALTIES:
            scores.field1 = request.data.get("field1", 0)
            scores.field2 = request.data.get("field2", 0)
            scores.field3 = request.data.get("field3", 0)
            scores.field4 = request.data.get("field4", 0)
            scores.field5 = request.data.get("field5", 0)
            scores.field6 = request.data.get("field6", 0)
            scores.field7 = request.data.get("field7", 0)
        elif scores.sheetType == ScoresheetEnum.REDESIGN:
            scores.field1 = request.data.get("field1", 0)
            scores.field2 = request.data.get("field2", 0)
            scores.field3 = request.data.get("field3", 0)
            scores.field4 = request.data.get("field4", 0)
            scores.field5 = request.data.get("field5", 0)
            scores.field6 = request.data.get("field6", 0)
            scores.field7 = request.data.get("field7", 0)
            scores.field9 = request.data.get("field9", "")
        elif scores.sheetType == ScoresheetEnum.CHAMPIONSHIP:
            # Championship scoresheets: fields 1-42
            # Fields 1-8: Machine Design
            # Field 9: Machine Design comment
            # Fields 10-17: Presentation  
            # Field 18: Presentation comment
            # Fields 19-25: General Penalties
            # Fields 26-42: Run Penalties
            for i in range(1, 43):
                if i == 9 or i == 18:
                    # Comment fields
                    scores.__setattr__(f"field{i}", request.data.get(f"field{i}", ""))
                else:
                    # Score/penalty fields
                    scores.__setattr__(f"field{i}", request.data.get(f"field{i}", 0))
        else:
            scores.field1 = request.data.get("field1", 0)
            scores.field2 = request.data.get("field2", 0)
            scores.field3 = request.data.get("field3", 0)
            scores.field4 = request.data.get("field4", 0)
            scores.field5 = request.data.get("field5", 0)
            scores.field6 = request.data.get("field6", 0)
            scores.field7 = request.data.get("field7", 0)
            scores.field8 = request.data.get("field8", 0)
            scores.field9 = request.data.get("field9", "")
            if scores.sheetType == ScoresheetEnum.RUNPENALTIES:
                scores.field10 = request.data.get("field10", 0)
                scores.field11 = request.data.get("field11", 0)
                scores.field12 = request.data.get("field12", 0)
                scores.field13 = request.data.get("field13", 0)
                scores.field14 = request.data.get("field14", 0)
                scores.field15 = request.data.get("field15", 0)
                scores.field16 = request.data.get("field16", 0)
                scores.field17 = request.data.get("field17", 0)
        scores.save()
        
        # Trigger tabulation recalculation asynchronously for all scoresheet types when submitted
        if scores.isSubmitted:
            try:
                # Get the team ID from the mapping
                team_mapping = MapScoresheetToTeamJudge.objects.filter(scoresheetid=scores.id).first()
                if team_mapping:
                    # Get the contest ID for this team
                    contest_mapping = MapContestToTeam.objects.filter(teamid=team_mapping.teamid).first()
                    if contest_mapping:
                        # Schedule tabulation asynchronously to avoid blocking the response
                        import threading
                        from .tabulation import recompute_totals_and_ranks
                        
                        def async_tabulation():
                            try:
                                recompute_totals_and_ranks(contest_mapping.contestid)
                            except Exception as e:
                                pass
                        
                        # Run tabulation in background thread
                        threading.Thread(target=async_tabulation, daemon=True).start()
            except Exception as tab_error:
                # Don't fail the request if tabulation fails
                pass
        
        serializer = ScoresheetSerializer(instance=scores)
        return Response({"edit_score_sheets": serializer.data})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def update_scores(request):
    try:
        scores = get_object_or_404(Scoresheet, id=request.data["id"])
        
        # Update isSubmitted field if provided
        if "isSubmitted" in request.data:
            scores.isSubmitted = request.data["isSubmitted"]
        if scores.sheetType == ScoresheetEnum.OTHERPENALTIES:
            scores.field1 = request.data.get("field1") or 0
            scores.field2 = request.data.get("field2") or 0
            scores.field3 = request.data.get("field3") or 0
            scores.field4 = request.data.get("field4") or 0
            scores.field5 = request.data.get("field5") or 0
            scores.field6 = request.data.get("field6") or 0
            scores.field7 = request.data.get("field7") or 0
        elif scores.sheetType == ScoresheetEnum.REDESIGN:
            scores.field1 = request.data.get("field1") or 0
            scores.field2 = request.data.get("field2") or 0
            scores.field3 = request.data.get("field3") or 0
            scores.field4 = request.data.get("field4") or 0
            scores.field5 = request.data.get("field5") or 0
            scores.field6 = request.data.get("field6") or 0
            scores.field7 = request.data.get("field7") or 0
            scores.field9 = request.data.get("field9") or ""
        elif scores.sheetType == ScoresheetEnum.CHAMPIONSHIP:
            # Championship structure: fields 1-9 = Machine Design, fields 10-18 = Presentation
            # Machine Design fields 1-9 (field9 is CharField for comments)
            scores.field1 = request.data.get("field1") or 0
            scores.field2 = request.data.get("field2") or 0
            scores.field3 = request.data.get("field3") or 0
            scores.field4 = request.data.get("field4") or 0
            scores.field5 = request.data.get("field5") or 0
            scores.field6 = request.data.get("field6") or 0
            scores.field7 = request.data.get("field7") or 0
            scores.field8 = request.data.get("field8") or 0
            scores.field9 = request.data.get("field9") or ""  # Machine Design comment
            # Presentation fields 10-18
            scores.field10 = request.data.get("field10") or 0
            scores.field11 = request.data.get("field11") or 0
            scores.field12 = request.data.get("field12") or 0
            scores.field13 = request.data.get("field13") or 0
            scores.field14 = request.data.get("field14") or 0
            scores.field15 = request.data.get("field15") or 0
            scores.field16 = request.data.get("field16") or 0
            scores.field17 = request.data.get("field17") or 0
            scores.field18 = request.data.get("field18") or ""  # Presentation comment
            # Penalty fields 19-42 (General Penalties: 19-25, Run Penalties: 26-42)
            scores.field19 = request.data.get("field19") or 0
            scores.field20 = request.data.get("field20") or 0
            scores.field21 = request.data.get("field21") or 0
            scores.field22 = request.data.get("field22") or 0
            scores.field23 = request.data.get("field23") or 0
            scores.field24 = request.data.get("field24") or 0
            scores.field25 = request.data.get("field25") or 0
            scores.field26 = request.data.get("field26") or 0
            scores.field27 = request.data.get("field27") or 0
            scores.field28 = request.data.get("field28") or 0
            scores.field29 = request.data.get("field29") or 0
            scores.field30 = request.data.get("field30") or 0
            scores.field31 = request.data.get("field31") or 0
            scores.field32 = request.data.get("field32") or 0
            scores.field33 = request.data.get("field33") or 0
            scores.field34 = request.data.get("field34") or 0
            scores.field35 = request.data.get("field35") or 0
            scores.field36 = request.data.get("field36") or 0
            scores.field37 = request.data.get("field37") or 0
            scores.field38 = request.data.get("field38") or 0
            scores.field39 = request.data.get("field39") or 0
            scores.field40 = request.data.get("field40") or 0
            scores.field41 = request.data.get("field41") or 0
            scores.field42 = request.data.get("field42") or 0
        else:
            scores.field1 = request.data.get("field1") or 0
            scores.field2 = request.data.get("field2") or 0
            scores.field3 = request.data.get("field3") or 0
            scores.field4 = request.data.get("field4") or 0
            scores.field5 = request.data.get("field5") or 0
            scores.field6 = request.data.get("field6") or 0
            scores.field7 = request.data.get("field7") or 0
            scores.field8 = request.data.get("field8") or 0
            scores.field9 = request.data.get("field9") or ""
            if scores.sheetType == ScoresheetEnum.RUNPENALTIES:
                scores.field10 = request.data.get("field10") or 0
                scores.field11 = request.data.get("field11") or 0
                scores.field12 = request.data.get("field12") or 0
                scores.field13 = request.data.get("field13") or 0
                scores.field14 = request.data.get("field14") or 0
                scores.field15 = request.data.get("field15") or 0
                scores.field16 = request.data.get("field16") or 0
                scores.field17 = request.data.get("field17") or 0
            
        scores.save()
        
        # Reload from database to verify save
        scores.refresh_from_db()
        
        serializer = ScoresheetSerializer(instance=scores)
        
        # If this is a championship scoresheet submission, trigger tabulation recalculation asynchronously
        if scores.sheetType == ScoresheetEnum.CHAMPIONSHIP and scores.isSubmitted:
            try:
                # Get the team ID from the mapping
                team_mapping = MapScoresheetToTeamJudge.objects.filter(scoresheetid=scores.id).first()
                if team_mapping:
                    # Get the contest ID for this team
                    contest_mapping = MapContestToTeam.objects.filter(teamid=team_mapping.teamid).first()
                    if contest_mapping:
                        # Schedule tabulation asynchronously to avoid blocking the response
                        import threading
                        from .tabulation import recompute_totals_and_ranks
                        
                        def async_tabulation():
                            try:
                                recompute_totals_and_ranks(contest_mapping.contestid)
                            except Exception as e:
                                pass
                        
                        # Run tabulation in background thread
                        threading.Thread(target=async_tabulation, daemon=True).start()
            except Exception as tab_error:
                # Don't fail the request if tabulation fails
                pass
        
        return Response({"updated_sheet": serializer.data})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def edit_score_sheet_field(request):
    sheet = get_object_or_404(Scoresheet, id=request.data["id"])

    field_name = ""
    if isinstance(request.data["field"], int):
        field_name = "field"+str(request.data["field"])
    else:
        field_name = request.data["field"]

    if hasattr(sheet, field_name):
        setattr(sheet, field_name, request.data["new_value"])
        sheet.save()
        serializer = ScoresheetSerializer(instance=sheet)
        return Response({"score_sheet": serializer.data}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid field"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_score_sheet(request, scores_id):
    scores = get_object_or_404(Scoresheet, id=scores_id)
    scores.delete()
    return Response({"detail": "Score Sheet deleted successfully."}, status=status.HTTP_200_OK)

def create_score_sheet_helper(map_data):
    serializer = ScoresheetSerializer(data=map_data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data
    else:
        return {"errors": serializer.errors}


def create_base_score_sheet(sheet_type):
    base_score_data = {
        "sheetType": sheet_type,
        "isSubmitted": False,
        "field1": 0.0,
        "field2": 0.0,
        "field3": 0.0,
        "field4": 0.0,
        "field5": 0.0,
        "field6": 0.0,
        "field7": 0.0,
        "field8": 0.0,
        "field9": "",
    }

    serializer = ScoresheetSerializer(data=base_score_data)
    if serializer.is_valid():
        score_sheet = serializer.save()
        return score_sheet
    else:
        raise ValidationError(serializer.errors)

def create_base_score_sheet_runpenalties():
    base_score_data = {
        "sheetType": 4,
        "isSubmitted": False,
        "field1": 0.0,
        "field2": 0.0,
        "field3": 0.0,
        "field4": 0.0,
        "field5": 0.0,
        "field6": 0.0,
        "field7": 0.0,
        "field8": 0.0,
        "field9": "",
        "field10": 0.0,
        "field11": 0.0,
        "field12": 0.0,
        "field13": 0.0,
        "field14": 0.0,
        "field15": 0.0,
        "field16": 0.0,
        "field17": 0.0
    }

    serializer = ScoresheetSerializer(data=base_score_data)
    if serializer.is_valid():
        score_sheet = serializer.save()
        return score_sheet
    else:
        raise ValidationError(serializer.errors)

def create_base_score_sheet_otherpenalties():
    base_score_data = {
        "sheetType": 5,
        "isSubmitted": False,
        "field1": 0.0,
        "field2": 0.0,
        "field3": 0.0,
        "field4": 0.0,
        "field5": 0.0,
        "field6": 0.0,
        "field7": 0.0,
        "field9": ""
    }

    serializer = ScoresheetSerializer(data=base_score_data)
    if serializer.is_valid():
        score_sheet = serializer.save()
        return score_sheet
    else:
        raise ValidationError(serializer.errors)

def create_base_score_sheet_Redesign():
    base_score_data = {
        "sheetType": 6,
        "isSubmitted": False,
        "field1": 0.0,
        "field2": 0.0,
        "field3": 0.0,
        "field4": 0.0,
        "field5": 0.0,
        "field6": 0.0,
        "field7": 0.0,
        "field9": ""
    }

    serializer = ScoresheetSerializer(data=base_score_data)
    if serializer.is_valid():
        score_sheet = serializer.save()
        return score_sheet
    else:
        raise ValidationError(serializer.errors)

def create_base_score_sheet_Championship():
    base_score_data = {
        "sheetType": 7,
        "isSubmitted": False,
        # Machine Design fields 1-8
        "field1": 0.0, "field2": 0.0, "field3": 0.0, "field4": 0.0,
        "field5": 0.0, "field6": 0.0, "field7": 0.0, "field8": 0.0,
        # Machine Design comment field 9
        "field9": "",
        # Presentation fields 10-17
        "field10": 0.0, "field11": 0.0, "field12": 0.0, "field13": 0.0,
        "field14": 0.0, "field15": 0.0, "field16": 0.0, "field17": 0.0,
        # Presentation comment field 18
        "field18": "",
        # Penalty fields 19-42 (General Penalties: 19-25, Run Penalties: 26-42)
        "field19": 0.0, "field20": 0.0, "field21": 0.0, "field22": 0.0, "field23": 0.0, "field24": 0.0, "field25": 0.0,
        "field26": 0.0, "field27": 0.0, "field28": 0.0, "field29": 0.0, "field30": 0.0, "field31": 0.0, "field32": 0.0,
        "field33": 0.0, "field34": 0.0, "field35": 0.0, "field36": 0.0, "field37": 0.0, "field38": 0.0, "field39": 0.0,
        "field40": 0.0, "field41": 0.0, "field42": 0.0
    }

    serializer = ScoresheetSerializer(data=base_score_data)
    if serializer.is_valid():
        score_sheet = serializer.save()
        return score_sheet
    else:
        raise ValidationError(serializer.errors)

def create_sheets_for_teams_in_cluster(judge_id, cluster_id, presentation, journal, mdo, runpenalties, otherpenalties, redesign, championship):
    try:
        
        # Fetch all mappings for the teams in the cluster
        mappings = MapClusterToTeam.objects.filter(clusterid=cluster_id)
        # Check if mappings exist
        if not mappings.exists():
            # For championship/redesign clusters, it's okay to have no teams initially
            # Teams will be added later when championship advancement occurs
            return []  # Return empty list instead of raising error

        # Extract all the team_ids from the mappings
        team_ids = mappings.values_list('teamid', flat=True)

        # Fetch all teams with the given team_ids
        teams_in_cluster = Teams.objects.filter(id__in=team_ids)
        # List to store responses
        created_score_sheets = []

        for team in teams_in_cluster:
            
            # Check for existing scoresheets to prevent duplicates
            existing_mappings = MapScoresheetToTeamJudge.objects.filter(
                teamid=team.id, 
                judgeid=judge_id
            )
            
            if runpenalties:
                # Check if runpenalties scoresheet already exists
                existing_runpenalties = existing_mappings.filter(sheetType=4).exists()
                if not existing_runpenalties:
                    sheet = create_base_score_sheet_runpenalties()
                    map_data = {"teamid": team.id, "judgeid": judge_id, "scoresheetid": sheet.id, "sheetType": 4}
                    map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                    if map_serializer.is_valid():
                        map_serializer.save()
                        created_score_sheets.append({
                            "team_id": team.id,
                            "judge_id": judge_id,
                            "scoresheet_id": sheet.id,
                            "sheetType": 4
                        })
                    else:
                        raise ValidationError(map_serializer.errors)
                else:
                    pass
            if otherpenalties:
                # Check if otherpenalties scoresheet already exists
                existing_otherpenalties = existing_mappings.filter(sheetType=5).exists()
                if not existing_otherpenalties:
                    sheet = create_base_score_sheet_otherpenalties()
                    map_data = {"teamid": team.id, "judgeid": judge_id, "scoresheetid": sheet.id, "sheetType": 5}
                    map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                    if map_serializer.is_valid():
                        map_serializer.save()
                        created_score_sheets.append({
                            "team_id": team.id,
                            "judge_id": judge_id,
                            "scoresheet_id": sheet.id,
                            "sheetType": 5
                        })
                    else:
                        raise ValidationError(map_serializer.errors)
                else:
                    pass
            if presentation:
                # Check if presentation scoresheet already exists
                existing_presentation = existing_mappings.filter(sheetType=1).exists()
                if not existing_presentation:
                    sheet = create_base_score_sheet(1)
                    map_data = {"teamid": team.id, "judgeid": judge_id, "scoresheetid": sheet.id, "sheetType": 1}
                    map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                    if map_serializer.is_valid():
                        map_serializer.save()
                        created_score_sheets.append({
                            "team_id": team.id,
                            "judge_id": judge_id,
                            "scoresheet_id": sheet.id,
                            "sheetType": 1
                        })
                    else:
                        raise ValidationError(map_serializer.errors)
                else:
                    pass
            if journal:
                # Check if journal scoresheet already exists
                existing_journal = existing_mappings.filter(sheetType=2).exists()
                if not existing_journal:
                    sheet = create_base_score_sheet(2)
                    map_data = {"teamid": team.id, "judgeid": judge_id, "scoresheetid": sheet.id, "sheetType": 2}
                    map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                    if map_serializer.is_valid():
                        map_serializer.save()
                        created_score_sheets.append({
                            "team_id": team.id,
                            "judge_id": judge_id,
                            "scoresheet_id": sheet.id,
                            "sheetType": 2
                        })
                    else:
                        raise ValidationError(map_serializer.errors)
                else:
                    pass
            if redesign:
                # Check if redesign scoresheet already exists
                existing_redesign = existing_mappings.filter(sheetType=6).exists()
                if not existing_redesign:
                    sheet = create_base_score_sheet_Redesign()
                    map_data = {"teamid": team.id, "judgeid": judge_id, "scoresheetid": sheet.id, "sheetType": 6}
                    map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                    if map_serializer.is_valid():
                        map_serializer.save()
                        created_score_sheets.append({
                            "team_id": team.id,
                            "judge_id": judge_id,
                            "scoresheet_id": sheet.id,
                            "sheetType": 6
                        })
                    else:
                        raise ValidationError(map_serializer.errors)
                else:
                    pass
            if mdo:
                # Check if MDO scoresheet already exists
                existing_mdo = existing_mappings.filter(sheetType=3).exists()
                if not existing_mdo:
                    sheet = create_base_score_sheet(3)
                    map_data = {"teamid": team.id, "judgeid": judge_id, "scoresheetid": sheet.id, "sheetType": 3}
                    map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                    if map_serializer.is_valid():
                        map_serializer.save()
                        created_score_sheets.append({
                            "team_id": team.id,
                            "judge_id": judge_id,
                            "scoresheet_id": sheet.id,
                            "sheetType": 3
                        })
                    else:
                        raise ValidationError(map_serializer.errors)
                else:
                    pass
            if championship:
                # Check if championship scoresheet already exists
                existing_championship = existing_mappings.filter(sheetType=7).exists()
                if not existing_championship:
                    try:
                        sheet = create_base_score_sheet(7)
                        map_data = {"teamid": team.id, "judgeid": judge_id, "scoresheetid": sheet.id, "sheetType": 7}
                        map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                        if map_serializer.is_valid():
                            map_serializer.save()
                            created_score_sheets.append({
                                "team_id": team.id,
                                "judge_id": judge_id,
                                "scoresheet_id": sheet.id,
                                "sheetType": 7
                            })
                        else:
                            raise ValidationError(map_serializer.errors)
                    except Exception as e:
                        raise e
                else:
                    pass
            else:
                pass

        return created_score_sheets

    except Exception as e:
        raise ValidationError({"detail": str(e)})

def create_score_sheets_for_team(team, judges):
    created_score_sheets = []
    for judge in judges:
        # Create score sheets for each type (Presentation, Journal, Machine Design, Penalties) based on the judge's role
        if judge.presentation:
            score_sheet = create_base_score_sheet(ScoresheetEnum.PRESENTATION)
            MapScoresheetToTeamJudge.objects.create(
                teamid=team.id, judgeid=judge.id, scoresheetid=score_sheet.id, sheetType=ScoresheetEnum.PRESENTATION
            )
            created_score_sheets.append(score_sheet)
        if judge.journal:
            score_sheet = create_base_score_sheet(ScoresheetEnum.JOURNAL)
            MapScoresheetToTeamJudge.objects.create(
                teamid=team.id, judgeid=judge.id, scoresheetid=score_sheet.id, sheetType=ScoresheetEnum.JOURNAL
            )
            created_score_sheets.append(score_sheet)
        if judge.mdo:
            score_sheet = create_base_score_sheet(ScoresheetEnum.MACHINEDESIGN)
            MapScoresheetToTeamJudge.objects.create(
                teamid=team.id, judgeid=judge.id, scoresheetid=score_sheet.id, sheetType=ScoresheetEnum.MACHINEDESIGN
            )
            created_score_sheets.append(score_sheet)
        if judge.runpenalties:
            score_sheet = create_base_score_sheet_runpenalties()
            MapScoresheetToTeamJudge.objects.create(
                teamid=team.id, judgeid=judge.id, scoresheetid=score_sheet.id, sheetType=ScoresheetEnum.RUNPENALTIES
            )
            created_score_sheets.append(score_sheet)
        if judge.otherpenalties:
            score_sheet = create_base_score_sheet_otherpenalties()
            MapScoresheetToTeamJudge.objects.create(
                teamid=team.id, judgeid=judge.id, scoresheetid=score_sheet.id, sheetType=ScoresheetEnum.OTHERPENALTIES
            )
            created_score_sheets.append(score_sheet)
        if judge.redesign:
            score_sheet = create_base_score_sheet_Redesign()
            MapScoresheetToTeamJudge.objects.create(
                teamid=team.id, judgeid=judge.id, scoresheetid=score_sheet.id, sheetType=ScoresheetEnum.REDESIGN
            )
        if judge.championship:
            score_sheet = create_base_score_sheet_Championship()
            MapScoresheetToTeamJudge.objects.create(
                teamid=team.id, judgeid=judge.id, scoresheetid=score_sheet.id, sheetType=ScoresheetEnum.CHAMPIONSHIP
            )
            created_score_sheets.append(score_sheet)
    return created_score_sheets

def get_scoresheet_id(judge_id, team_id, scoresheet_type):
    try:
        mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team_id, sheetType=scoresheet_type)
        scoresheet = Scoresheet.objects.get(id=mapping.scoresheetid)
        return scoresheet.id
    except Scoresheet.DoesNotExist:
        raise ValidationError({"error": "No scoresheet found"})

def delete_sheets_for_teams_in_cluster(judge_id, cluster_id,  presentation, journal, mdo,runpenalties, otherpenalties, redesign, championship):
    try:
        # Fetch all mappings for the teams in the cluster
        mappings = MapClusterToTeam.objects.filter(clusterid=cluster_id)

        # Check if mappings exist
        if not mappings.exists():
            # For championship/redesign clusters, it's okay to have no teams initially
            # Teams will be added later when championship advancement occurs
            return []  # Return empty list instead of raising error

        # Extract all the team_ids from the mappings
        team_ids = mappings.values_list('teamid', flat=True)

        # Fetch all teams with the given team_ids
        teams_in_cluster = Teams.objects.filter(id__in=team_ids)

        for team in teams_in_cluster:
            if runpenalties:
                try:
                    scoresheet_id = get_scoresheet_id(judge_id, team.id, 4)
                    scoresheet = Scoresheet.objects.get(id=scoresheet_id)
                    mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team.id, sheetType=4)
                    delete_score_sheet_mapping(mapping.id)  # Delete mapping
                    scoresheet.delete()  # Delete scoresheet
                except (ValidationError, Scoresheet.DoesNotExist, MapScoresheetToTeamJudge.DoesNotExist):
                    # Scoresheet doesn't exist, skip deletion
                    pass
            if otherpenalties:
                try:
                    scoresheet_id = get_scoresheet_id(judge_id, team.id, 5)
                    scoresheet = Scoresheet.objects.get(id=scoresheet_id)
                    mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team.id, sheetType=5)
                    delete_score_sheet_mapping(mapping.id)
                    scoresheet.delete()
                except (ValidationError, Scoresheet.DoesNotExist, MapScoresheetToTeamJudge.DoesNotExist):
                    pass
            if presentation:
                try:
                    scoresheet_id = get_scoresheet_id(judge_id, team.id, 1)
                    scoresheet = Scoresheet.objects.get(id=scoresheet_id)
                    mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team.id, sheetType=1)
                    delete_score_sheet_mapping(mapping.id)
                    scoresheet.delete()
                except (ValidationError, Scoresheet.DoesNotExist, MapScoresheetToTeamJudge.DoesNotExist):
                    pass
            if journal:
                try:
                    scoresheet_id = get_scoresheet_id(judge_id, team.id, 2)
                    scoresheet = Scoresheet.objects.get(id=scoresheet_id)
                    mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team.id, sheetType=2)
                    delete_score_sheet_mapping(mapping.id)
                    scoresheet.delete()
                except (ValidationError, Scoresheet.DoesNotExist, MapScoresheetToTeamJudge.DoesNotExist):
                    pass
            if redesign:
                try:
                    scoresheet_id = get_scoresheet_id(judge_id, team.id, 6)
                    scoresheet = Scoresheet.objects.get(id=scoresheet_id)
                    mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team.id, sheetType=6)
                    delete_score_sheet_mapping(mapping.id)
                    scoresheet.delete()
                except (ValidationError, Scoresheet.DoesNotExist, MapScoresheetToTeamJudge.DoesNotExist):
                    pass
            if mdo:
                try:
                    scoresheet_id = get_scoresheet_id(judge_id, team.id, 3)
                    scoresheet = Scoresheet.objects.get(id=scoresheet_id)
                    mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team.id, sheetType=3)
                    delete_score_sheet_mapping(mapping.id)
                    scoresheet.delete()
                except (ValidationError, Scoresheet.DoesNotExist, MapScoresheetToTeamJudge.DoesNotExist):
                    pass
            if championship:
                try:
                    scoresheet_id = get_scoresheet_id(judge_id, team.id, 7)
                    scoresheet = Scoresheet.objects.get(id=scoresheet_id)
                    mapping = MapScoresheetToTeamJudge.objects.get(judgeid=judge_id, teamid=team.id, sheetType=7)
                    delete_score_sheet_mapping(mapping.id)
                    scoresheet.delete()
                except (ValidationError, Scoresheet.DoesNotExist, MapScoresheetToTeamJudge.DoesNotExist):
                    pass

    except Exception as e:
        raise ValidationError({"detail": str(e)})
  
def make_sheets_for_team(teamid, clusterid):
    created_score_sheets = []
    try:
        judges = MapJudgeToCluster.objects.filter(clusterid=clusterid)  # get list of judge mappings
        for judge_map in judges:
            # Create score sheets for each type (Presentation, Journal, Machine Design, Run Penalties, Other Penalties) based on the judge's role
            judge = Judge.objects.get(id=judge_map.judgeid)  # get judge from judge mapping
            
            if judge.presentation:
                sheet = create_base_score_sheet(1)
                map_data = {"teamid": teamid, "judgeid": judge.id, "scoresheetid": sheet.id, "sheetType": 1}
                map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                if map_serializer.is_valid():
                    map_serializer.save()
                    created_score_sheets.append({
                        "team_id": teamid,
                        "judge_id": judge.id,
                        "scoresheet_id": sheet.id,
                        "sheetType": 1
                    })
                else:
                    raise ValidationError(map_serializer.errors)
            if judge.journal:
                sheet = create_base_score_sheet(2)
                map_data = {"teamid": teamid, "judgeid": judge.id, "scoresheetid": sheet.id, "sheetType": 2}
                map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                if map_serializer.is_valid():
                    map_serializer.save()
                    created_score_sheets.append({
                        "team_id": teamid,
                        "judge_id": judge.id,
                        "scoresheet_id": sheet.id,
                        "sheetType": 2
                    })
                else:
                    raise ValidationError(map_serializer.errors)
            if judge.mdo:
                sheet = create_base_score_sheet(3)
                map_data = {"teamid": teamid, "judgeid": judge.id, "scoresheetid": sheet.id, "sheetType": 3}
                map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
                if map_serializer.is_valid():
                    map_serializer.save()
                    created_score_sheets.append({
                        "team_id": teamid,
                        "judge_id": judge.id,
                        "scoresheet_id": sheet.id,
                        "sheetType": 3
                    })
                else:
                    raise ValidationError(map_serializer.errors)
        if judge.runpenalties:
            sheet = create_base_score_sheet_runpenalties()
            map_data = {"teamid": teamid, "judgeid": judge.id, "scoresheetid": sheet.id, "sheetType": 4}
            map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
            if map_serializer.is_valid():
                map_serializer.save()
                created_score_sheets.append({
                    "team_id": teamid,
                    "judge_id": judge.id,
                    "scoresheet_id": sheet.id,
                    "sheetType": 4
                })
        if judge.otherpenalties:
            sheet = create_base_score_sheet_otherpenalties()
            map_data = {"teamid": teamid, "judgeid": judge.id, "scoresheetid": sheet.id, "sheetType": 5}
            map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
            if map_serializer.is_valid():
                map_serializer.save()
                created_score_sheets.append({
                    "team_id": teamid,
                    "judge_id": judge.id,
                    "scoresheet_id": sheet.id,
                    "sheetType": 5
                })
            else:
                raise ValidationError(map_serializer.errors)
        if judge.redesign:
            sheet = create_base_score_sheet_Redesign()
            map_data = {"teamid": teamid, "judgeid": judge.id, "scoresheetid": sheet.id, "sheetType": 6}
            map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
            if map_serializer.is_valid():
                map_serializer.save()
                created_score_sheets.append({
                    "team_id": teamid,
                    "judge_id": judge.id,
                    "scoresheet_id": sheet.id,
                    "sheetType": 6
                })
        if judge.championship:
            sheet = create_base_score_sheet(7)
            map_data = {"teamid": teamid, "judgeid": judge.id, "scoresheetid": sheet.id, "sheetType": 7}
            map_serializer = MapScoreSheetToTeamJudgeSerializer(data=map_data)
            if map_serializer.is_valid():
                map_serializer.save()
                created_score_sheets.append({
                    "team_id": teamid,
                    "judge_id": judge.id,
                    "scoresheet_id": sheet.id,
                    "sheetType": 7
                })
            else:
                raise ValidationError(map_serializer.errors)

    except Exception as e:
        raise e

    return created_score_sheets


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_scoresheet_details_by_team(request, team_id):
    scoresheet_mappings = MapScoresheetToTeamJudge.objects.filter(teamid=team_id)
    scoresheets = Scoresheet.objects.filter(id__in=scoresheet_mappings.values_list('scoresheetid', flat=True))
    presentation_scoresheet_details = [[] for _ in range(9)]
    journal_scoresheet_details = [[] for _ in range(9)]
    machinedesign_scoresheet_details = [[] for _ in range(9)]
    run_penalties_scoresheet_details = [[] for _ in range(16)]
    other_penalties_scoresheet_details = [[] for _ in range(7)]
    redesign_scoresheet_details = [[] for _ in range(8)]
    championship_scoresheet_details = [[] for _ in range(42)]  # Fields 1-42 (including penalty fields 19-42)
    for sheet in scoresheets:
      if sheet.sheetType == 1:
        presentation_scoresheet_details[0].append(sheet.field1)
        presentation_scoresheet_details[1].append(sheet.field2)
        presentation_scoresheet_details[2].append(sheet.field3)
        presentation_scoresheet_details[3].append(sheet.field4)
        presentation_scoresheet_details[4].append(sheet.field5)
        presentation_scoresheet_details[5].append(sheet.field6)
        presentation_scoresheet_details[6].append(sheet.field7)
        presentation_scoresheet_details[7].append(sheet.field8)
        presentation_scoresheet_details[8].append(sheet.field9)
      elif sheet.sheetType == 2:
        journal_scoresheet_details[0].append(sheet.field1)
        journal_scoresheet_details[1].append(sheet.field2)
        journal_scoresheet_details[2].append(sheet.field3)
        journal_scoresheet_details[3].append(sheet.field4)
        journal_scoresheet_details[4].append(sheet.field5)
        journal_scoresheet_details[5].append(sheet.field6)
        journal_scoresheet_details[6].append(sheet.field7)
        journal_scoresheet_details[7].append(sheet.field8)
        journal_scoresheet_details[8].append(sheet.field9)
      elif sheet.sheetType == 3:
        machinedesign_scoresheet_details[0].append(sheet.field1)
        machinedesign_scoresheet_details[1].append(sheet.field2)
        machinedesign_scoresheet_details[2].append(sheet.field3)
        machinedesign_scoresheet_details[3].append(sheet.field4)
        machinedesign_scoresheet_details[4].append(sheet.field5)
        machinedesign_scoresheet_details[5].append(sheet.field6)
        machinedesign_scoresheet_details[6].append(sheet.field7)
        machinedesign_scoresheet_details[7].append(sheet.field8)
        machinedesign_scoresheet_details[8].append(sheet.field9)
      elif sheet.sheetType == 4:
        run_penalties_scoresheet_details[0].append(sheet.field1)
        run_penalties_scoresheet_details[1].append(sheet.field2)
        run_penalties_scoresheet_details[2].append(sheet.field3)
        run_penalties_scoresheet_details[3].append(sheet.field4)
        run_penalties_scoresheet_details[4].append(sheet.field5)
        run_penalties_scoresheet_details[5].append(sheet.field6)
        run_penalties_scoresheet_details[6].append(sheet.field7)
        run_penalties_scoresheet_details[7].append(sheet.field8)
        run_penalties_scoresheet_details[8].append(sheet.field10)
        run_penalties_scoresheet_details[9].append(sheet.field11)
        run_penalties_scoresheet_details[10].append(sheet.field12)
        run_penalties_scoresheet_details[11].append(sheet.field13)
        run_penalties_scoresheet_details[12].append(sheet.field14)
        run_penalties_scoresheet_details[13].append(sheet.field15)
        run_penalties_scoresheet_details[14].append(sheet.field16)
        run_penalties_scoresheet_details[15].append(sheet.field17)
      
      elif sheet.sheetType == 5:
        other_penalties_scoresheet_details[0].append(sheet.field1)
        other_penalties_scoresheet_details[1].append(sheet.field2)
        other_penalties_scoresheet_details[2].append(sheet.field3)
        other_penalties_scoresheet_details[3].append(sheet.field4)
        other_penalties_scoresheet_details[4].append(sheet.field5)
        other_penalties_scoresheet_details[5].append(sheet.field6)
        other_penalties_scoresheet_details[6].append(sheet.field7)
      elif sheet.sheetType == 6:
        redesign_scoresheet_details[0].append(sheet.field1)
        redesign_scoresheet_details[1].append(sheet.field2)
        redesign_scoresheet_details[2].append(sheet.field3)
        redesign_scoresheet_details[3].append(sheet.field4)
        redesign_scoresheet_details[4].append(sheet.field5)
        redesign_scoresheet_details[5].append(sheet.field6)
        redesign_scoresheet_details[6].append(sheet.field7)
        redesign_scoresheet_details[7].append(sheet.field9)
      elif sheet.sheetType == 7:
        
        # Machine Design fields 1-8 (field9 is CharField for comments)
        championship_scoresheet_details[0].append(sheet.field1)
        championship_scoresheet_details[1].append(sheet.field2)
        championship_scoresheet_details[2].append(sheet.field3)
        championship_scoresheet_details[3].append(sheet.field4)
        championship_scoresheet_details[4].append(sheet.field5)
        championship_scoresheet_details[5].append(sheet.field6)
        championship_scoresheet_details[6].append(sheet.field7)
        championship_scoresheet_details[7].append(sheet.field8)
        championship_scoresheet_details[8].append(sheet.field9)  # Machine Design comment
        # Presentation fields 10-17 (field18 is CharField for comments)
        championship_scoresheet_details[9].append(sheet.field10)
        championship_scoresheet_details[10].append(sheet.field11)
        championship_scoresheet_details[11].append(sheet.field12)
        championship_scoresheet_details[12].append(sheet.field13)
        championship_scoresheet_details[13].append(sheet.field14)
        championship_scoresheet_details[14].append(sheet.field15)
        championship_scoresheet_details[15].append(sheet.field16)
        championship_scoresheet_details[16].append(sheet.field17)
        championship_scoresheet_details[17].append(sheet.field18)  # Presentation comment
        
        # Penalty fields 19-42 (General Penalties: 19-25, Run Penalties: 26-42)
        championship_scoresheet_details[18].append(sheet.field19)  # General Penalty 1
        championship_scoresheet_details[19].append(sheet.field20)  # General Penalty 2
        championship_scoresheet_details[20].append(sheet.field21)  # General Penalty 3
        championship_scoresheet_details[21].append(sheet.field22)  # General Penalty 4
        championship_scoresheet_details[22].append(sheet.field23)  # General Penalty 5
        championship_scoresheet_details[23].append(sheet.field24)  # General Penalty 6
        championship_scoresheet_details[24].append(sheet.field25)  # General Penalty 7
        championship_scoresheet_details[25].append(sheet.field26)  # Run Penalty 1
        championship_scoresheet_details[26].append(sheet.field27)  # Run Penalty 2
        championship_scoresheet_details[27].append(sheet.field28)  # Run Penalty 3
        championship_scoresheet_details[28].append(sheet.field29)  # Run Penalty 4
        championship_scoresheet_details[29].append(sheet.field30)  # Run Penalty 5
        championship_scoresheet_details[30].append(sheet.field31)  # Run Penalty 6
        championship_scoresheet_details[31].append(sheet.field32)  # Run Penalty 7
        championship_scoresheet_details[32].append(sheet.field33)  # Run Penalty 8
        championship_scoresheet_details[33].append(sheet.field34)  # Run Penalty 9
        championship_scoresheet_details[34].append(sheet.field35)  # Run Penalty 10
        championship_scoresheet_details[35].append(sheet.field36)  # Run Penalty 11
        championship_scoresheet_details[36].append(sheet.field37)  # Run Penalty 12
        championship_scoresheet_details[37].append(sheet.field38)  # Run Penalty 13
        championship_scoresheet_details[38].append(sheet.field39)  # Run Penalty 14
        championship_scoresheet_details[39].append(sheet.field40)  # Run Penalty 15
        championship_scoresheet_details[40].append(sheet.field41)  # Run Penalty 16
        championship_scoresheet_details[41].append(sheet.field42)  # Run Penalty 17

    presentation_scoresheet_response = {
      "1": presentation_scoresheet_details[0],
      "2": presentation_scoresheet_details[1],
      "3": presentation_scoresheet_details[2],
      "4": presentation_scoresheet_details[3],
      "5": presentation_scoresheet_details[4],
      "6": presentation_scoresheet_details[5],
      "7": presentation_scoresheet_details[6],
      "8": presentation_scoresheet_details[7],
      "9": presentation_scoresheet_details[8],
    }
    journal_scoresheet_response = {
      "1": journal_scoresheet_details[0],
      "2": journal_scoresheet_details[1],
      "3": journal_scoresheet_details[2],
      "4": journal_scoresheet_details[3],
      "5": journal_scoresheet_details[4],
      "6": journal_scoresheet_details[5],
      "7": journal_scoresheet_details[6],
      "8": journal_scoresheet_details[7],
      "9": journal_scoresheet_details[8],
    }
    machinedesign_scoresheet_response = {
      "1": machinedesign_scoresheet_details[0],
      "2": machinedesign_scoresheet_details[1],
      "3": machinedesign_scoresheet_details[2],
      "4": machinedesign_scoresheet_details[3],
      "5": machinedesign_scoresheet_details[4],
      "6": machinedesign_scoresheet_details[5],
      "7": machinedesign_scoresheet_details[6],
      "8": machinedesign_scoresheet_details[7],
      "9": machinedesign_scoresheet_details[8],
    }

    runpenalties_scoresheet_response = {
      "1": run_penalties_scoresheet_details[0],
      "2": run_penalties_scoresheet_details[1],
      "3": run_penalties_scoresheet_details[2],
      "4": run_penalties_scoresheet_details[3],
      "5": run_penalties_scoresheet_details[4],
      "6": run_penalties_scoresheet_details[5],
      "7": run_penalties_scoresheet_details[6],
      "8": run_penalties_scoresheet_details[7],
      "10": run_penalties_scoresheet_details[8],
      "11": run_penalties_scoresheet_details[9],
      "12": run_penalties_scoresheet_details[10],
      "13": run_penalties_scoresheet_details[11],
      "14": run_penalties_scoresheet_details[12],
      "15": run_penalties_scoresheet_details[13],
      "16": run_penalties_scoresheet_details[14],
      "17": run_penalties_scoresheet_details[15],
  }
    otherpenalties_scoresheet_response = {
      "1": other_penalties_scoresheet_details[0],
      "2": other_penalties_scoresheet_details[1],
      "3": other_penalties_scoresheet_details[2],
      "4": other_penalties_scoresheet_details[3],
      "5": other_penalties_scoresheet_details[4],
      "6": other_penalties_scoresheet_details[5],
      "7": other_penalties_scoresheet_details[6],
    }
    redesign_scoresheet_response = {
      "1": redesign_scoresheet_details[0],
      "2": redesign_scoresheet_details[1],
      "3": redesign_scoresheet_details[2],
      "4": redesign_scoresheet_details[3],
      "5": redesign_scoresheet_details[4],
      "6": redesign_scoresheet_details[5],
      "7": redesign_scoresheet_details[6],
      "8": redesign_scoresheet_details[7],
    }

    championship_scoresheet_response = {
      "field1": championship_scoresheet_details[0],   # Machine Design 1
      "field2": championship_scoresheet_details[1],   # Machine Design 2
      "field3": championship_scoresheet_details[2],   # Machine Design 3
      "field4": championship_scoresheet_details[3],   # Machine Design 4
      "field5": championship_scoresheet_details[4],   # Machine Design 5
      "field6": championship_scoresheet_details[5],   # Machine Design 6
      "field7": championship_scoresheet_details[6],   # Machine Design 7
      "field8": championship_scoresheet_details[7],   # Machine Design 8
      "field9": championship_scoresheet_details[8],   # Machine Design Comment
      "field10": championship_scoresheet_details[9],  # Presentation 1
      "field11": championship_scoresheet_details[10], # Presentation 2
      "field12": championship_scoresheet_details[11], # Presentation 3
      "field13": championship_scoresheet_details[12], # Presentation 4
      "field14": championship_scoresheet_details[13], # Presentation 5
      "field15": championship_scoresheet_details[14], # Presentation 6
      "field16": championship_scoresheet_details[15], # Presentation 7
      "field17": championship_scoresheet_details[16], # Presentation 8
      "field18": championship_scoresheet_details[17], # Presentation Comment
      # Penalty fields 19-42
      "field19": championship_scoresheet_details[18],  # General Penalty 1
      "field20": championship_scoresheet_details[19],  # General Penalty 2
      "field21": championship_scoresheet_details[20],  # General Penalty 3
      "field22": championship_scoresheet_details[21],  # General Penalty 4
      "field23": championship_scoresheet_details[22],  # General Penalty 5
      "field24": championship_scoresheet_details[23],  # General Penalty 6
      "field25": championship_scoresheet_details[24],  # General Penalty 7
      "field26": championship_scoresheet_details[25],  # Run Penalty 1
      "field27": championship_scoresheet_details[26],  # Run Penalty 2
      "field28": championship_scoresheet_details[27],  # Run Penalty 3
      "field29": championship_scoresheet_details[28],  # Run Penalty 4
      "field30": championship_scoresheet_details[29],  # Run Penalty 5
      "field31": championship_scoresheet_details[30],  # Run Penalty 6
      "field32": championship_scoresheet_details[31],  # Run Penalty 7
      "field33": championship_scoresheet_details[32],  # Run Penalty 8
      "field34": championship_scoresheet_details[33],  # Run Penalty 9
      "field35": championship_scoresheet_details[34],  # Run Penalty 10
      "field36": championship_scoresheet_details[35],  # Run Penalty 11
      "field37": championship_scoresheet_details[36],  # Run Penalty 12
      "field38": championship_scoresheet_details[37],  # Run Penalty 13
      "field39": championship_scoresheet_details[38],  # Run Penalty 14
      "field40": championship_scoresheet_details[39],  # Run Penalty 15
      "field41": championship_scoresheet_details[40],  # Run Penalty 16
      "field42": championship_scoresheet_details[41],  # Run Penalty 17
    }
    

    return Response({
      "1": presentation_scoresheet_response,
      "2": journal_scoresheet_response,
      "3": machinedesign_scoresheet_response,
      "4": runpenalties_scoresheet_response,
      "5": otherpenalties_scoresheet_response,
      "6": redesign_scoresheet_response,
      "7": championship_scoresheet_response
    }, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_scoresheet_details_for_contest(request):
    contest = get_object_or_404(Contest, id=request.data["contestid"])
    team_mappings = MapContestToTeam.objects.filter(contestid=contest.id)
    team_responses = {}
    for mapping in team_mappings:
        team = get_object_or_404(Teams, id=mapping.teamid)
        scoresheet_mappings = MapScoresheetToTeamJudge.objects.filter(teamid=team.id)
        scoresheets = Scoresheet.objects.filter(id__in=scoresheet_mappings.values_list('scoresheetid', flat=True))
        presentation_scoresheet_details = [[] for _ in range(9)]
        journal_scoresheet_details = [[] for _ in range(9)]
        machinedesign_scoresheet_details = [[] for _ in range(9)]
        run_penalties_scoresheet_details = [[] for _ in range(16)]
        other_penalties_scoresheet_details = [[] for _ in range(7)]
        redesign_scoresheet_details = [[] for _ in range(8)]
        championship_scoresheet_details = [[] for _ in range(42)]  # Fields 1-42 (including penalty fields 19-42)
        for sheet in scoresheets:
            if sheet.sheetType == 1:
                presentation_scoresheet_details[0].append(sheet.field1)
                presentation_scoresheet_details[1].append(sheet.field2)
                presentation_scoresheet_details[2].append(sheet.field3)
                presentation_scoresheet_details[3].append(sheet.field4)
                presentation_scoresheet_details[4].append(sheet.field5)
                presentation_scoresheet_details[5].append(sheet.field6)
                presentation_scoresheet_details[6].append(sheet.field7)
                presentation_scoresheet_details[7].append(sheet.field8)
                presentation_scoresheet_details[8].append(sheet.field9)
            elif sheet.sheetType == 2:
                journal_scoresheet_details[0].append(sheet.field1)
                journal_scoresheet_details[1].append(sheet.field2)
                journal_scoresheet_details[2].append(sheet.field3)
                journal_scoresheet_details[3].append(sheet.field4)
                journal_scoresheet_details[4].append(sheet.field5)
                journal_scoresheet_details[5].append(sheet.field6)
                journal_scoresheet_details[6].append(sheet.field7)
                journal_scoresheet_details[7].append(sheet.field8)
                journal_scoresheet_details[8].append(sheet.field9)
            elif sheet.sheetType == 3:
                machinedesign_scoresheet_details[0].append(sheet.field1)
                machinedesign_scoresheet_details[1].append(sheet.field2)
                machinedesign_scoresheet_details[2].append(sheet.field3)
                machinedesign_scoresheet_details[3].append(sheet.field4)
                machinedesign_scoresheet_details[4].append(sheet.field5)
                machinedesign_scoresheet_details[5].append(sheet.field6)
                machinedesign_scoresheet_details[6].append(sheet.field7)
                machinedesign_scoresheet_details[7].append(sheet.field8)
                machinedesign_scoresheet_details[8].append(sheet.field9)
            elif sheet.sheetType == 4:
                run_penalties_scoresheet_details[0].append(sheet.field1)
                run_penalties_scoresheet_details[1].append(sheet.field2)
                run_penalties_scoresheet_details[2].append(sheet.field3)
                run_penalties_scoresheet_details[3].append(sheet.field4)
                run_penalties_scoresheet_details[4].append(sheet.field5)
                run_penalties_scoresheet_details[5].append(sheet.field6)
                run_penalties_scoresheet_details[6].append(sheet.field7)
                run_penalties_scoresheet_details[7].append(sheet.field8)
                run_penalties_scoresheet_details[8].append(sheet.field10)
                run_penalties_scoresheet_details[9].append(sheet.field11)
                run_penalties_scoresheet_details[10].append(sheet.field12)
                run_penalties_scoresheet_details[11].append(sheet.field13)
                run_penalties_scoresheet_details[12].append(sheet.field14)
                run_penalties_scoresheet_details[13].append(sheet.field15)
                run_penalties_scoresheet_details[14].append(sheet.field16)
                run_penalties_scoresheet_details[15].append(sheet.field17)
            
            elif sheet.sheetType == 5:
                other_penalties_scoresheet_details[0].append(sheet.field1)
                other_penalties_scoresheet_details[1].append(sheet.field2)
                other_penalties_scoresheet_details[2].append(sheet.field3)
                other_penalties_scoresheet_details[3].append(sheet.field4)
                other_penalties_scoresheet_details[4].append(sheet.field5)
                other_penalties_scoresheet_details[5].append(sheet.field6)
                other_penalties_scoresheet_details[6].append(sheet.field7)
            elif sheet.sheetType == 6:
                redesign_scoresheet_details[0].append(sheet.field1)
                redesign_scoresheet_details[1].append(sheet.field2)
                redesign_scoresheet_details[2].append(sheet.field3)
                redesign_scoresheet_details[3].append(sheet.field4)
                redesign_scoresheet_details[4].append(sheet.field5)
                redesign_scoresheet_details[5].append(sheet.field6)
                redesign_scoresheet_details[6].append(sheet.field7)
                redesign_scoresheet_details[7].append(sheet.field9)
            elif sheet.sheetType == 7:
                # Machine Design fields 1-8 (field9 is CharField for comments)
                championship_scoresheet_details[0].append(sheet.field1)
                championship_scoresheet_details[1].append(sheet.field2)
                championship_scoresheet_details[2].append(sheet.field3)
                championship_scoresheet_details[3].append(sheet.field4)
                championship_scoresheet_details[4].append(sheet.field5)
                championship_scoresheet_details[5].append(sheet.field6)
                championship_scoresheet_details[6].append(sheet.field7)
                championship_scoresheet_details[7].append(sheet.field8)
                championship_scoresheet_details[8].append(sheet.field9)  # Machine Design comment
                # Presentation fields 10-17 (field18 is CharField for comments)
                championship_scoresheet_details[9].append(sheet.field10)
                championship_scoresheet_details[10].append(sheet.field11)
                championship_scoresheet_details[11].append(sheet.field12)
                championship_scoresheet_details[12].append(sheet.field13)
                championship_scoresheet_details[13].append(sheet.field14)
                championship_scoresheet_details[14].append(sheet.field15)
                championship_scoresheet_details[15].append(sheet.field16)
                championship_scoresheet_details[16].append(sheet.field17)
                championship_scoresheet_details[17].append(sheet.field18)  # Presentation comment
                
                # Penalty fields 19-42 (General Penalties: 19-25, Run Penalties: 26-42)
                championship_scoresheet_details[18].append(sheet.field19)  # General Penalty 1
                championship_scoresheet_details[19].append(sheet.field20)  # General Penalty 2
                championship_scoresheet_details[20].append(sheet.field21)  # General Penalty 3
                championship_scoresheet_details[21].append(sheet.field22)  # General Penalty 4
                championship_scoresheet_details[22].append(sheet.field23)  # General Penalty 5
                championship_scoresheet_details[23].append(sheet.field24)  # General Penalty 6
                championship_scoresheet_details[24].append(sheet.field25)  # General Penalty 7
                championship_scoresheet_details[25].append(sheet.field26)  # Run Penalty 1
                championship_scoresheet_details[26].append(sheet.field27)  # Run Penalty 2
                championship_scoresheet_details[27].append(sheet.field28)  # Run Penalty 3
                championship_scoresheet_details[28].append(sheet.field29)  # Run Penalty 4
                championship_scoresheet_details[29].append(sheet.field30)  # Run Penalty 5
                championship_scoresheet_details[30].append(sheet.field31)  # Run Penalty 6
                championship_scoresheet_details[31].append(sheet.field32)  # Run Penalty 7
                championship_scoresheet_details[32].append(sheet.field33)  # Run Penalty 8
                championship_scoresheet_details[33].append(sheet.field34)  # Run Penalty 9
                championship_scoresheet_details[34].append(sheet.field35)  # Run Penalty 10
                championship_scoresheet_details[35].append(sheet.field36)  # Run Penalty 11
                championship_scoresheet_details[36].append(sheet.field37)  # Run Penalty 12
                championship_scoresheet_details[37].append(sheet.field38)  # Run Penalty 13
                championship_scoresheet_details[38].append(sheet.field39)  # Run Penalty 14
                championship_scoresheet_details[39].append(sheet.field40)  # Run Penalty 15
                championship_scoresheet_details[40].append(sheet.field41)  # Run Penalty 16
                championship_scoresheet_details[41].append(sheet.field42)  # Run Penalty 17
            


        presentation_scoresheet_response = {
          "1": presentation_scoresheet_details[0],
          "2": presentation_scoresheet_details[1],
          "3": presentation_scoresheet_details[2],
          "4": presentation_scoresheet_details[3],
          "5": presentation_scoresheet_details[4],
          "6": presentation_scoresheet_details[5],
          "7": presentation_scoresheet_details[6],
          "8": presentation_scoresheet_details[7],
          "9": presentation_scoresheet_details[8],
        }
        journal_scoresheet_response = {
          "1": journal_scoresheet_details[0],
          "2": journal_scoresheet_details[1],
          "3": journal_scoresheet_details[2],
          "4": journal_scoresheet_details[3],
          "5": journal_scoresheet_details[4],
          "6": journal_scoresheet_details[5],
          "7": journal_scoresheet_details[6],
          "8": journal_scoresheet_details[7],
          "9": journal_scoresheet_details[8],
        }
        machinedesign_scoresheet_response = {
          "1": machinedesign_scoresheet_details[0],
          "2": machinedesign_scoresheet_details[1],
          "3": machinedesign_scoresheet_details[2],
          "4": machinedesign_scoresheet_details[3],
          "5": machinedesign_scoresheet_details[4],
          "6": machinedesign_scoresheet_details[5],
          "7": machinedesign_scoresheet_details[6],
          "8": machinedesign_scoresheet_details[7],
          "9": machinedesign_scoresheet_details[8],
        }
        runpenalties_scoresheet_response = {
          "1": run_penalties_scoresheet_details[0],
          "2": run_penalties_scoresheet_details[1],
          "3": run_penalties_scoresheet_details[2],
          "4": run_penalties_scoresheet_details[3],
          "5": run_penalties_scoresheet_details[4],
          "6": run_penalties_scoresheet_details[5],
          "7": run_penalties_scoresheet_details[6],
          "8": run_penalties_scoresheet_details[7],
          "10": run_penalties_scoresheet_details[8],
          "11": run_penalties_scoresheet_details[9],
          "12": run_penalties_scoresheet_details[10],
          "13": run_penalties_scoresheet_details[11],
          "14": run_penalties_scoresheet_details[12],
          "15": run_penalties_scoresheet_details[13],
          "16": run_penalties_scoresheet_details[14],
          "17": run_penalties_scoresheet_details[15],
        }
        otherpenalties_scoresheet_response = {
          "1": other_penalties_scoresheet_details[0],
          "2": other_penalties_scoresheet_details[1],
          "3": other_penalties_scoresheet_details[2],
          "4": other_penalties_scoresheet_details[3],
          "5": other_penalties_scoresheet_details[4],
          "6": other_penalties_scoresheet_details[5],
          "7": other_penalties_scoresheet_details[6],
        }
        redesign_scoresheet_response = {
            "1": redesign_scoresheet_details[0],
            "2": redesign_scoresheet_details[1],
            "3": redesign_scoresheet_details[2],
            "4": redesign_scoresheet_details[3],
            "5": redesign_scoresheet_details[4],
            "6": redesign_scoresheet_details[5],
            "7": redesign_scoresheet_details[6],
            "8": redesign_scoresheet_details[7],
        }
        championship_scoresheet_response = {
            "field1": championship_scoresheet_details[0],   # Machine Design 1
            "field2": championship_scoresheet_details[1],   # Machine Design 2
            "field3": championship_scoresheet_details[2],   # Machine Design 3
            "field4": championship_scoresheet_details[3],   # Machine Design 4
            "field5": championship_scoresheet_details[4],   # Machine Design 5
            "field6": championship_scoresheet_details[5],   # Machine Design 6
            "field7": championship_scoresheet_details[6],   # Machine Design 7
            "field8": championship_scoresheet_details[7],   # Machine Design 8
            "field9": championship_scoresheet_details[8],   # Machine Design Comment
            "field10": championship_scoresheet_details[9],  # Presentation 1
            "field11": championship_scoresheet_details[10], # Presentation 2
            "field12": championship_scoresheet_details[11], # Presentation 3
            "field13": championship_scoresheet_details[12], # Presentation 4
            "field14": championship_scoresheet_details[13], # Presentation 5
            "field15": championship_scoresheet_details[14], # Presentation 6
            "field16": championship_scoresheet_details[15], # Presentation 7
            "field17": championship_scoresheet_details[16], # Presentation 8
            "field18": championship_scoresheet_details[17], # Presentation Comment
            # Penalty fields 19-42
            "field19": championship_scoresheet_details[18],  # General Penalty 1
            "field20": championship_scoresheet_details[19],  # General Penalty 2
            "field21": championship_scoresheet_details[20],  # General Penalty 3
            "field22": championship_scoresheet_details[21],  # General Penalty 4
            "field23": championship_scoresheet_details[22],  # General Penalty 5
            "field24": championship_scoresheet_details[23],  # General Penalty 6
            "field25": championship_scoresheet_details[24],  # General Penalty 7
            "field26": championship_scoresheet_details[25],  # Run Penalty 1
            "field27": championship_scoresheet_details[26],  # Run Penalty 2
            "field28": championship_scoresheet_details[27],  # Run Penalty 3
            "field29": championship_scoresheet_details[28],  # Run Penalty 4
            "field30": championship_scoresheet_details[29],  # Run Penalty 5
            "field31": championship_scoresheet_details[30],  # Run Penalty 6
            "field32": championship_scoresheet_details[31],  # Run Penalty 7
            "field33": championship_scoresheet_details[32],  # Run Penalty 8
            "field34": championship_scoresheet_details[33],  # Run Penalty 9
            "field35": championship_scoresheet_details[34],  # Run Penalty 10
            "field36": championship_scoresheet_details[35],  # Run Penalty 11
            "field37": championship_scoresheet_details[36],  # Run Penalty 12
            "field38": championship_scoresheet_details[37],  # Run Penalty 13
            "field39": championship_scoresheet_details[38],  # Run Penalty 14
            "field40": championship_scoresheet_details[39],  # Run Penalty 15
            "field41": championship_scoresheet_details[40],  # Run Penalty 16
            "field42": championship_scoresheet_details[41],  # Run Penalty 17
        }

        team_responses[team.id] = {
            "team_id": team.id,
            "1": presentation_scoresheet_response,
            "2": journal_scoresheet_response,
            "3": machinedesign_scoresheet_response,
            "4": runpenalties_scoresheet_response,
            "5": otherpenalties_scoresheet_response,
            "6": redesign_scoresheet_response,
            "7": championship_scoresheet_response
        }

    return Response({"teams": team_responses}, status=status.HTTP_200_OK)


def create_scoresheets_for_judges_in_cluster(cluster_id):
    """
    Create scoresheets for all judges in a cluster when teams are added.
    This is called after teams are moved to championship/redesign clusters.
    """
    try:
        
        # Get all judges in this cluster
        judge_mappings = MapJudgeToCluster.objects.filter(clusterid=cluster_id)
        
        # Get all teams in this cluster
        team_mappings = MapClusterToTeam.objects.filter(clusterid=cluster_id)
        
        if len(judge_mappings) == 0:
            return []
        
        if len(team_mappings) == 0:
            return []
        
        created_scoresheets = []
        
        for judge_mapping in judge_mappings:
            try:
                judge = Judge.objects.get(id=judge_mapping.judgeid)
                
                # Create scoresheets for this judge and all teams in the cluster
                
                sheets = create_sheets_for_teams_in_cluster(
                    judge.id,
                    cluster_id,
                    judge.presentation,
                    judge.journal,
                    judge.mdo,
                    judge.runpenalties,
                    judge.otherpenalties,
                    judge.redesign,
                    judge.championship
                )
                
                created_scoresheets.extend(sheets)
                
            except Judge.DoesNotExist:
                continue
            except Exception as e:
                continue
        
        return created_scoresheets
        
    except Exception as e:
        raise ValidationError({"detail": str(e)})
