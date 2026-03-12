"""
Market Sizing Controller — generation + verification for market sizing data.

Public API
----------
generate_market_sizings(...)       -> list[EnhancedMarketSizing | None]
generate_and_verify(...)           -> dict  (corrected_market_sizings)
"""
import json
import asyncio
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from output_formats import EnhancedMarketSizing, market_sizing_output_format
from llm_call import get_ai_response, LLM_MODEL
import dynamic_prompt_creator
from market_sizing_verification import verify_all_market_sizings


# ============================================================================
# GENERATION
# ============================================================================

def generate_market_sizings(
    segments: List[Dict[str, Any]],
    jtbd: Any,
    idea: Any,
    location: str,
    max_segments: int = 3,
) -> List[Optional[EnhancedMarketSizing]]:
    """
    Generate market sizing for the top N segments (default: first 3 = high-struggle).
    Builds a prompt per segment on the fly, then runs all calls in parallel.

    Returns:
        List of EnhancedMarketSizing objects (None for failed calls).
    """
    target_segments = segments[:max_segments]

    def _call_one(seg: Dict[str, Any]) -> Optional[EnhancedMarketSizing]:
        try:
            prompt = dynamic_prompt_creator.build_market_sizing_prompt(seg, jtbd, idea, location)
            raw = get_ai_response(
                prompt=prompt,
                llm_model=LLM_MODEL,
                output_format=market_sizing_output_format,
                dynamic_thinking_level="medium",
                grounding=True,
            )
            parsed = json.loads(raw)
            return EnhancedMarketSizing.model_validate(parsed)
        except Exception as e:
            print(f"[SD] Market sizing call failed: {e}")
            return None

    # Run calls in parallel using threads
    with ThreadPoolExecutor(max_workers=min(len(target_segments), 4)) as pool:
        results = list(pool.map(_call_one, target_segments))

    return results


# ============================================================================
# GENERATE + VERIFY (FULL PIPELINE)
# ============================================================================

def generate_and_verify(
    segments: List[Dict[str, Any]],
    jtbd: Any,
    idea: Any,
    location: str,
    max_segments: int = 3,
) -> Dict[str, Any]:
    """
    Full pipeline: generate market sizings, then verify them.

    Args:
        segments:           Corrected segment dicts (typically high-struggle).
        jtbd:               Job-To-Be-Done / signal context.
        idea:               Business idea context.
        location:           Target market location.
        max_segments:       How many segments to size.

    Returns:
        Dict with:
          - corrected_market_sizings: List of verified/corrected market sizing dicts
    """
    # Step 1: Generate
    ms_results = generate_market_sizings(
        segments=segments,
        jtbd=jtbd,
        idea=idea,
        location=location,
        max_segments=max_segments,
    )

    # Convert Pydantic models to plain dicts
    raw_dicts = [
        json.loads(r.model_dump_json()) if r else None
        for r in ms_results
    ]
    valid_sizings = [ms for ms in raw_dicts if ms]

    # Step 2: Verify
    jtbd_dict = jtbd if isinstance(jtbd, dict) else None
    idea_dict = idea if isinstance(idea, dict) else None

    verification_result = verify_all_market_sizings(
        market_sizings=valid_sizings,
        jtbd=jtbd_dict,
        idea=idea_dict,
    )

    return {
        "corrected_market_sizings": verification_result["corrected_market_sizings"],
    }
