# Generated manually for FeedbackDisplaySettings model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emdcbackend', '0006_ballot_mapawardtocontest_mapballottovote_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeedbackDisplaySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contestid', models.IntegerField(unique=True)),
                ('show_presentation_comments', models.BooleanField(default=True)),
                ('show_journal_comments', models.BooleanField(default=True)),
                ('show_machinedesign_comments', models.BooleanField(default=True)),
                ('show_redesign_comments', models.BooleanField(default=True)),
                ('show_championship_comments', models.BooleanField(default=True)),
                ('show_penalty_comments', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
