from django.db import migrations, models


def populate_cluster_assignment_flags(apps, schema_editor):
    MapJudgeToCluster = apps.get_model("emdcbackend", "MapJudgeToCluster")
    MapContestToCluster = apps.get_model("emdcbackend", "MapContestToCluster")
    Judge = apps.get_model("emdcbackend", "Judge")

    def as_bool(value):
        return bool(value) if value is not None else False

    for assignment in MapJudgeToCluster.objects.all():
        judge = Judge.objects.filter(id=assignment.judgeid).first()
        contest_map = MapContestToCluster.objects.filter(clusterid=assignment.clusterid).first()

        contest_id = contest_map.contestid if contest_map and contest_map.contestid else assignment.contestid

        if judge:
            presentation = as_bool(getattr(judge, "presentation", False))
            journal = as_bool(getattr(judge, "journal", False))
            mdo = as_bool(getattr(judge, "mdo", False))
            runpenalties = as_bool(getattr(judge, "runpenalties", False))
            otherpenalties = as_bool(getattr(judge, "otherpenalties", False))
            redesign = as_bool(getattr(judge, "redesign", False))
            championship = as_bool(getattr(judge, "championship", False))
        else:
            presentation = as_bool(getattr(assignment, "presentation", False))
            journal = as_bool(getattr(assignment, "journal", False))
            mdo = as_bool(getattr(assignment, "mdo", False))
            runpenalties = as_bool(getattr(assignment, "runpenalties", False))
            otherpenalties = as_bool(getattr(assignment, "otherpenalties", False))
            redesign = as_bool(getattr(assignment, "redesign", False))
            championship = as_bool(getattr(assignment, "championship", False))

        MapJudgeToCluster.objects.filter(pk=assignment.pk).update(
            contestid=contest_id,
            presentation=presentation,
            journal=journal,
            mdo=mdo,
            runpenalties=runpenalties,
            otherpenalties=otherpenalties,
            redesign=redesign,
            championship=championship,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("emdcbackend", "0020_rolesharedpassword"),
    ]

    operations = [
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="presentation",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="journal",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="mdo",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="runpenalties",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="otherpenalties",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="redesign",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="championship",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mapjudgetocluster",
            name="contestid",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(populate_cluster_assignment_flags, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="mapjudgetocluster",
            unique_together={("judgeid", "clusterid")},
        ),
    ]

