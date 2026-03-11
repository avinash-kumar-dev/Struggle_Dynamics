"""
LLM interaction layer using Google Gemini with high thinking, grounding, and URL context
"""
import os
import asyncio
from typing import Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
LLM_MODEL = "gemini-3-flash-preview"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")


def get_ai_response(
    prompt: str,
    output_format: Type[BaseModel],
    grounding: bool = True,
    thinking_level: str = "high",
    url_context: list = None,
    model: str = None
) -> Optional[BaseModel]:
    """
    Synchronous LLM call with thinking and optional grounding.

    Returns:
        Parsed Pydantic model instance, or None on error.
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        active_model = model or LLM_MODEL

        tools = []
        if grounding:
            tools.append(types.Tool(google_search=types.GoogleSearch()))
        tools.append(types.Tool(url_context={}))

        thinking_level_map = {
            "high": types.ThinkingLevel.HIGH,
            "medium": types.ThinkingLevel.MEDIUM,
            "low": types.ThinkingLevel.LOW,
            "minimal": types.ThinkingLevel.MINIMAL,
        }
        thinking_level_enum = thinking_level_map.get(thinking_level.lower(), types.ThinkingLevel.HIGH)

        config_params = {
            "response_mime_type": "application/json",
            "response_json_schema": output_format.model_json_schema(),
            "thinking_config": types.ThinkingConfig(thinkingLevel=thinking_level_enum),
            "tools": tools,
        }

        final_prompt = prompt
        if url_context:
            url_section = "\n\n# REFERENCE URLs (Model will retrieve content from these)\n\n"
            for i, url in enumerate(url_context, 1):
                url_section += f"{i}. {url}\n"
            url_section += "\n**Use these URLs as primary sources for market data, pricing, and competitive intelligence.**\n\n"
            final_prompt = url_section + prompt

        response = client.models.generate_content(
            model=active_model,
            contents=final_prompt,
            config=types.GenerateContentConfig(**config_params)
        )

        if response and response.text:
            return output_format.model_validate_json(response.text)
        return None

    except Exception as e:
        print(f"❌ LLM Error: {e}")
        return None


async def get_ai_response_async(
    prompt: str,
    output_format: Type[BaseModel],
    grounding: bool = True,
    thinking_level: str = "high",
    url_context: list = None,
    model: str = None
) -> Optional[BaseModel]:
    """
    Async LLM call — runs sync call in a thread pool.

    Returns:
        Parsed Pydantic model instance, or None on error.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: get_ai_response(prompt, output_format, grounding, thinking_level, url_context, model)
    )


async def batch_ai_responses(
    prompts: list[str],
    output_format: Type[BaseModel],
    grounding: bool = True,
    thinking_level: str = "high",
    url_context: list = None,
    batch_size: int = 4
) -> list[Optional[BaseModel]]:
    """
    Execute multiple LLM calls in parallel batches.

    Returns:
        List of parsed responses (None for failed calls).
    """
    all_results = []

    for i in range(0, len(prompts), batch_size):
        batch_prompts = prompts[i:i + batch_size]
        tasks = [
            get_ai_response_async(p, output_format, grounding, thinking_level, url_context)
            for p in batch_prompts
        ]
        batch_results = await asyncio.gather(*tasks)
        all_results.extend(batch_results)

    return all_results
