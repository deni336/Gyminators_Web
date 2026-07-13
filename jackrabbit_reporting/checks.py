from django.conf import settings
from django.core.checks import Error, Warning, register

from jackrabbit_reporting.security import MIN_WEBHOOK_TOKEN_LENGTH, usable_webhook_token


@register()
def reporting_configuration_check(app_configs, **kwargs):
    if not settings.JACKRABBIT_REPORTING_ENABLED:
        return []
    messages = []
    organization_id = str(settings.JACKRABBIT_ORG_ID).strip()
    if not organization_id or len(organization_id) > 20 or not organization_id.isdigit():
        messages.append(
            Error(
                "JACKRABBIT_ORG_ID must be a numeric identifier of at most 20 digits.",
                id="jackrabbit_reporting.E001",
            )
        )
    current_token = settings.JACKRABBIT_WEBHOOK_TOKEN
    previous_token = settings.JACKRABBIT_WEBHOOK_PREVIOUS_TOKEN
    if not current_token:
        if not settings.DEBUG:
            messages.append(
                Warning(
                    "Jackrabbit event ingestion is disabled until JACKRABBIT_WEBHOOK_TOKEN is configured.",
                    id="jackrabbit_reporting.W001",
                )
            )
    elif not usable_webhook_token(current_token):
        messages.append(
            Warning(
                "JACKRABBIT_WEBHOOK_TOKEN must be a generated secret of at least "
                f"{MIN_WEBHOOK_TOKEN_LENGTH} characters, not an example value.",
                id="jackrabbit_reporting.W002",
            )
        )
    if previous_token and not usable_webhook_token(previous_token):
        messages.append(
            Warning(
                "JACKRABBIT_WEBHOOK_PREVIOUS_TOKEN is ignored because it is too short "
                "or is a known example value.",
                id="jackrabbit_reporting.W003",
            )
        )
    if current_token and previous_token and current_token == previous_token:
        messages.append(
            Warning(
                "Current and previous Jackrabbit webhook tokens are identical; clear "
                "the previous value unless a rotation is in progress.",
                id="jackrabbit_reporting.W004",
            )
        )
    if settings.JACKRABBIT_WEBHOOK_MAX_BODY_BYTES < 1024:
        messages.append(Error("JACKRABBIT_WEBHOOK_MAX_BODY_BYTES must be at least 1024.", id="jackrabbit_reporting.E002"))
    return messages
