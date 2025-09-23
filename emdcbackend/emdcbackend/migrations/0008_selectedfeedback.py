# Generated manually for SelectedFeedback model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emdcbackend', '0007_feedbackdisplaysettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='SelectedFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contestid', models.IntegerField()),
                ('scoresheet_id', models.IntegerField()),
                ('is_selected', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='selectedfeedback',
            unique_together={('contestid', 'scoresheet_id')},
        ),
    ]
