MIN_WEBHOOK_TOKEN_LENGTH = 32

KNOWN_PLACEHOLDER_TOKENS = {
    "replace-with-a-random-secret-of-at-least-32-characters",
    "temporary-check-token-with-more-than-32-characters",
}


def usable_webhook_token(value):
    value = str(value or "").strip()
    return len(value) >= MIN_WEBHOOK_TOKEN_LENGTH and value not in KNOWN_PLACEHOLDER_TOKENS
