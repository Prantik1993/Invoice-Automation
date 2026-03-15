import json
from pathlib import Path
from openai import AsyncOpenAI
from app.config import settings
from app.core.exceptions import LLMExtractionError
from app.core.logging import get_logger

logger = get_logger(__name__)
client = AsyncOpenAI(api_key=settings.openai_api_key)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extraction_prompt.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text()


async def extract_invoice_fields(text: str) -> dict:
    """Send invoice text to OpenAI and get structured fields back."""
    prompt = PROMPT_TEMPLATE.format(invoice_text=text)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
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
