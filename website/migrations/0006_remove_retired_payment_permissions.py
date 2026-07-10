from django.db import migrations


def remove_retired_payment_permissions(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="website",
        model__in=(
            "membershipplan",
            "customer",
            "subscription",
            "payment",
            "paymentrequest",
            "webhookevent",
            "reportingpermission",
        ),
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("website", "0005_jackrabbit_only"),
    ]

    operations = [
        migrations.RunPython(remove_retired_payment_permissions, migrations.RunPython.noop),
    ]
