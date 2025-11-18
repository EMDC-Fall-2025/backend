from django.core.management.base import BaseCommand
from emdcbackend.models import Scoresheet, ScoresheetEnum, MapScoresheetToTeamJudge


class Command(BaseCommand):
    help = 'Fix existing championship scoresheets to use the correct field structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete all existing championship scoresheets instead of updating them',
        )

    def handle(self, *args, **options):
        if options['delete']:
            self.delete_championship_scoresheets()
        else:
            self.update_championship_scoresheets()

    def delete_championship_scoresheets(self):
        """Delete all existing championship scoresheets and their mappings"""
        self.stdout.write('Deleting all existing championship scoresheets...')
        
        # Get all championship scoresheets
        championship_sheets = Scoresheet.objects.filter(sheetType=ScoresheetEnum.CHAMPIONSHIP)
        count = championship_sheets.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No championship scoresheets found to delete.'))
            return
        
        # Delete mappings first
        mappings = MapScoresheetToTeamJudge.objects.filter(sheetType=ScoresheetEnum.CHAMPIONSHIP)
        mappings_count = mappings.count()
        mappings.delete()
        
        # Delete scoresheets
        championship_sheets.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {count} championship scoresheets and {mappings_count} mappings.'
            )
        )

    def update_championship_scoresheets(self):
        """Update existing championship scoresheets to use the correct field structure"""
        self.stdout.write('Updating existing championship scoresheets...')
        
        # Get all championship scoresheets
        championship_sheets = Scoresheet.objects.filter(sheetType=ScoresheetEnum.CHAMPIONSHIP)
        count = championship_sheets.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No championship scoresheets found to update.'))
            return
        
        updated_count = 0
        
        for sheet in championship_sheets:
            updated = False
            
            # Reset all fields to default values
            # Machine Design fields 1-8 (scores)
            for i in range(1, 9):
                field_name = f'field{i}'
                if getattr(sheet, field_name) is not None:
                    setattr(sheet, field_name, 0.0)
                    updated = True
            
            # Machine Design comment field 9
            if sheet.field9 is not None:
                sheet.field9 = ""
                updated = True
            
            # Presentation fields 10-17 (scores)
            for i in range(10, 18):
                field_name = f'field{i}'
                if getattr(sheet, field_name) is not None:
                    setattr(sheet, field_name, 0.0)
                    updated = True
            
            # Presentation comment field 18
            if sheet.field18 is not None:
                sheet.field18 = ""
                updated = True
            
            # Penalty fields 19-42
            for i in range(19, 43):
                field_name = f'field{i}'
                if hasattr(sheet, field_name):
                    if getattr(sheet, field_name) is not None:
                        setattr(sheet, field_name, 0.0)
                        updated = True
            
            if updated:
                sheet.save()
                updated_count += 1
                self.stdout.write(f'Updated scoresheet {sheet.id}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {updated_count} out of {count} championship scoresheets.'
            )
        )
