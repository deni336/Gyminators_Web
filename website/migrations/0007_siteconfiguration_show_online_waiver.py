from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0006_remove_retired_payment_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="show_online_waiver",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Keep disabled until the owner and attorney approve the agreement, privacy notice, "
                    "and retention policy. Enabling opens the public workflow and shows its website links."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="siteconfiguration",
            name="privacy_url",
            field=models.URLField(
                blank=True,
                help_text="Required before the public online-waiver workflow can be enabled.",
            ),
        ),
    ]
