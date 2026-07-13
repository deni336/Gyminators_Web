from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jackrabbit_reporting", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="jackrabbitclass",
            name="missed_syncs",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
