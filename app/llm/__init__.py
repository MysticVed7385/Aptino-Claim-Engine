"""
LLM interface module supporting OpenAI-compatible providers.
"""

from openai import OpenAI
from app.core.config import settings

# Initialize client using the custom base URL and API key from environment variables
client = None
if settings.LLM_API_KEY:
    client = OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=settings.LLM_TIMEOUT_S,
        max_retries=settings.LLM_MAX_RETRIES
    )


def call_llm(prompt: str, json_mode: bool = False) -> str:
    """Invokes the configured LLM endpoint via OpenAI-compatible Chat Completions API.

    Args:
        prompt: The input prompt string.
        json_mode: Enforces JSON output format if supported by provider.

    Returns:
        The text response from the model or a fallback string on error.
    """
    if not client or not settings.LLM_API_KEY:
        return (
            "{"
            '"search_queries": ["policy coverage limits", "exclusions"], '
            '"extracted_facts": {}, '
            '"missing_fields": [], '
            '"coverage_findings": ["LLM API key missing or unconfigured."], '
            '"applicable_limits": [], '
            '"missing_evidence": [], '
            '"decision": "NEEDS_REVIEW", '
            '"confidence": 0.5'
            "}"
        )

    try:
        kwargs = {
            "model": settings.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.LLM_TEMPERATURE,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        return f"Error invoking LLM endpoint ({settings.LLM_MODEL}): {str(e)}"


__all__ = ["call_llm"]