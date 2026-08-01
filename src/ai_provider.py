"""AI text provider identifiers shared by configuration and services."""

AI_PROVIDER_GEMINI = "gemini"
AI_PROVIDER_GROK_CLI = "grok_cli"
AI_PROVIDER_MANAGED = "managed"
SUPPORTED_AI_PROVIDERS = (
    AI_PROVIDER_MANAGED,
    AI_PROVIDER_GROK_CLI,
)


def normalize_ai_provider(value: object, default: str = AI_PROVIDER_MANAGED) -> str:
    """Return a supported provider identifier."""
    normalized = str(value or "").strip().lower()
    if normalized in SUPPORTED_AI_PROVIDERS:
        return normalized
    return default
