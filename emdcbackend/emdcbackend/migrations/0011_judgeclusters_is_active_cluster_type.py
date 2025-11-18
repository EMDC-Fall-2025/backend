# Generated manually for robust championship implementation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emdcbackend', '0010_teams_advanced_to_championship_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='judgeclusters',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='judgeclusters',
            name='cluster_type',
            field=models.CharField(
                choices=[
                    ('preliminary', 'Preliminary'),
                    ('championship', 'Championship'),
                    ('redesign', 'Redesign')
                ],
                default='preliminary',
                max_length=20
            ),
        ),
    ]

