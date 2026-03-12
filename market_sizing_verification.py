"""
Market Sizing Verification for the Struggle Dynamics module.

Verifies population data (total_population, prevalence_rate, struggle_aware_count)
and pricing data (annual_price per tier) produced by market_sizing.py.

Public API
----------
verify_all_market_sizings(market_sizings, jtbd, idea) -> dict
"""

import json
import asyncio
from typing import List, Dict, Any, Optional

from output_formats import MarketVerificationLLMOutput
from helpers import validate_urls_async, sanitize_urls_in_output
from dynamic_prompt_creator import build_market_verification_prompt


# ============================================================================
# ASYNC VERIFY ONE SEGMENT
# ============================================================================

async def verify_market_sizing_async(
    market_sizing: Dict[str, Any],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Optional[MarketVerificationLLMOutput]:
    """
    Verify one market sizing dict asynchronously.

    Returns the LLM verification response with URL-validated sources,
    or None on error.
    """
    from llm_call import get_ai_response, LLM_MODEL
    from output_formats import market_verification_output_format

    segment_name = market_sizing.get("segment_name", "Unknown")
    prompt = build_market_verification_prompt(market_sizing, jtbd, idea)

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: get_ai_response(
                prompt=prompt,
                llm_model=LLM_MODEL,
                output_format=market_verification_output_format,
                dynamic_thinking_level="medium",
                grounding=True,
            )
        )

        parsed = json.loads(raw)
        llm_output = MarketVerificationLLMOutput.model_validate(parsed)

        # Validate verification_sources URLs in-place
        for fv in llm_output.fields:
            if fv.verification_sources:
                fv.verification_sources = await validate_urls_async(fv.verification_sources)

        return llm_output

    except Exception as e:
        print(f"   ❌ {segment_name}: Verification failed - {e}")
        return None


# ============================================================================
# BATCH VERIFY
# ============================================================================

async def verify_all_market_sizings_async(
    market_sizings: List[Dict[str, Any]],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Verify all market sizings in parallel batches.

    Returns:
        Dict with:
          - verification_responses: {segment_name: MarketVerificationLLMOutput}
          - corrected_market_sizings: list of corrected market sizing dicts
    """
    responses: Dict[str, MarketVerificationLLMOutput] = {}

    BATCH_SIZE = 3
    for i in range(0, len(market_sizings), BATCH_SIZE):
        batch = [ms for ms in market_sizings[i:i + BATCH_SIZE] if ms]

        tasks = [
            verify_market_sizing_async(ms, jtbd=jtbd, idea=idea)
            for ms in batch
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for j, result in enumerate(batch_results):
            seg_name = batch[j].get("segment_name", f"Segment {i+j+1}")
            if isinstance(result, Exception):
                print(f"   ❌ {seg_name}: Verification error - {result}")
            elif result is not None:
                responses[seg_name] = result

    corrected_sizings = _apply_corrections(market_sizings, responses)

    # Sanitize: remove all URLs that fail HTTP validation
    corrected_sizings = await sanitize_urls_in_output(corrected_sizings)

    return {
        "verification_responses": responses,
        "corrected_market_sizings": corrected_sizings,
    }


# ============================================================================
# SYNC WRAPPER
# ============================================================================

def verify_all_market_sizings(
    market_sizings: List[Dict[str, Any]],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Synchronous wrapper around verify_all_market_sizings_async."""
    return asyncio.run(verify_all_market_sizings_async(market_sizings, jtbd, idea))


# ============================================================================
# CORRECTIONS
# ============================================================================

def _apply_corrections(
    original_sizings: List[Dict[str, Any]],
    responses: Dict[str, MarketVerificationLLMOutput],
) -> List[Dict[str, Any]]:
    """
    Apply verified corrections back onto the original market sizing dicts.
    Works directly with LLM response objects — no intermediate result model needed.
    """
    corrected: List[Any] = []

    for sizing in original_sizings:
        if not sizing:
            corrected.append(None)
            continue

        seg_name = sizing.get("segment_name", "")
        cs = sizing.copy()

        if seg_name in responses:
            llm_output = responses[seg_name]
            pop = cs.get("struggle_aware_population", {})

            for fv in llm_output.fields:
                updated = (
                    fv.corrected_value
                    if fv.correction_needed and fv.corrected_value
                    else fv.verified_value
                )
                if fv.field_name == "total_population":
                    try:
                        pop["total_population"] = int(updated.replace(",", "").split()[0])
                    except Exception:
                        pass
                elif fv.field_name == "prevalence_rate":
                    try:
                        pop["prevalence_rate"] = float(updated.replace("%", "").split()[0]) / 100
                    except Exception:
                        pass
                elif fv.field_name == "struggle_aware_count":
                    try:
                        pop["struggle_aware_count"] = int(updated.replace(",", "").split()[0])
                    except Exception:
                        pass

                # Update existing source fields with verified sources if available
                if fv.field_name == "total_population" and fv.verification_sources:
                    pop["population_source"] = fv.verification_sources[0]
                    pop["population_source_urls"] = fv.verified_source_urls or pop.get("population_source_urls", [])
                elif fv.field_name == "prevalence_rate" and fv.verification_sources:
                    pop["prevalence_source"] = fv.verification_sources[0]
                    pop["prevalence_source_urls"] = fv.verified_source_urls or pop.get("prevalence_source_urls", [])

        corrected.append(cs)

    return corrected
