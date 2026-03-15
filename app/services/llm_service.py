import json
from functools import lru_cache
from pathlib import Path
from openai import AsyncOpenAI
from app.config import settings
from app.core.exceptions import LLMExtractionError
from app.core.logging import get_logger

logger = get_logger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extraction_prompt.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text()


@lru_cache(maxsize=1)
def _get_client() -> AsyncOpenAI:
    """Create the OpenAI client once, lazily.

    Deferred until first actual call so the key is read from .env at
    runtime rather than at import time. This means a missing key surfaces
    as a clear runtime error, not a silent import-time failure.
    """
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def extract_invoice_fields(text: str) -> dict:
    """Send invoice text to the configured LLM and return structured fields."""
    prompt = PROMPT_TEMPLATE.format(invoice_text=text)

    try:
        response = await _get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm_temperature,
        )

        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        logger.info("llm_extracted", vendor=data.get("vendor_name"), confidence=data.get("confidence"))
        return data

    except json.JSONDecodeError as e:
        logger.error("llm_json_parse_failed", error=str(e))
        raise LLMExtractionError(f"LLM returned invalid JSON: {e}")
    except Exception as e:
        logger.error("llm_extraction_failed", error=str(e))
        raise LLMExtractionError(f"OpenAI call failed: {e}")