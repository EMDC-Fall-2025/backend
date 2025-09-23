from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('emdcbackend', '0008_selectedfeedback'),
    ]

    operations = [
        migrations.DeleteModel(
            name='FeedbackDisplaySettings',
        ),
    ]


