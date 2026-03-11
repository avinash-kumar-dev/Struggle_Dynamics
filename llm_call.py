"""
LLM interaction layer for Struggle Dynamics using Google Gemini.
"""
import json
import time
import random
import os
from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = "gemini-3-flash-preview"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

GEMINI_TIMEOUT = 3 * 60 * 1000
llm_client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT))


def get_ai_response(prompt, llm_model, output_format, dynamic_thinking_level="low", grounding=False, url_context=None):
    """
    Core function to get AI response from Gemini with retry logic and JSON validation.
    """
    # Build config
    config = {
        "response_mime_type": "application/json",
        "response_schema": output_format,
        "thinking_config": types.ThinkingConfig(thinking_level=dynamic_thinking_level)
    }

    # Tools (grounding + url_context)
    tools = []
    if grounding:
        tools.append(types.Tool(google_search=types.GoogleSearch()))
    if url_context:
        tools.append(types.Tool(url_context={}))
    if tools:
        config["tools"] = tools

    # Prepend URLs to prompt
    final_prompt = prompt
    if url_context:
        url_section = "\n\n# REFERENCE URLs\n\n"
        for i, url in enumerate(url_context, 1):
            url_section += f"{i}. {url}\n"
        final_prompt = url_section + "\n" + prompt

    def make_request():
        return llm_client.models.generate_content(
            model=llm_model,
            contents=[final_prompt],
            config=config
        )

    max_json_retries = 3
    for json_attempt in range(max_json_retries):
        try:
            response = _call_with_backoff(make_request)
            response_text = response.text or ""
            json.loads(response_text)
            return response_text

        except json.JSONDecodeError:
            if json_attempt < max_json_retries - 1:
                continue
            break

        except Exception as e:
            if json_attempt < max_json_retries - 1:
                continue
            print(f"[SD] get_ai_response failed after {max_json_retries} attempts: {e}")
            break

    return json.dumps({
        "error": True,
        "message": "AI service temporarily unavailable. Please try again in a few minutes.",
    })


def _call_with_backoff(func, max_retries=5, base_delay=1, max_delay=60):
    """Retry with exponential backoff for transient API errors."""
    for attempt in range(max_retries):
        try:
            return func()
        except (ServerError, ClientError) as e:
            is_retryable = isinstance(e, ServerError) and hasattr(e, 'status_code') and e.status_code in [429, 500, 502, 503, 504]
            if not is_retryable or attempt == max_retries - 1:
                raise
            time.sleep(min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay))
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay))
    raise Exception("Max retries exceeded")

