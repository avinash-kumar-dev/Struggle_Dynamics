"""
Segment Controller — generation + verification for Struggle Dynamics segments.

Public API
----------
generate_segments(...)        -> StruggleDynamicsList | None
verify_segments(...)          -> dict  (verification_responses, corrected_segments)
generate_and_verify(...)      -> dict  (high_struggle_segments, peripheral_segments)
"""
import json
from typing import Union, Dict, List, Any, Optional

from output_formats import StruggleDynamicsList, struggle_dynamics_output_format
from llm_call import get_ai_response, LLM_MODEL
import dynamic_prompt_creator
from struggle_dynamics_verification import verify_all_sd_segments


def generate_segments(
    confirmed_user: str,
    confirmed_struggle: str,
    confirmed_solution: str,
    selected_signal: Union[str, Dict],
    user_profile_title: str,
    target_location: str,
    language_level: str = "STANDARD_BUSINESS",
    url_context: list = None,
) -> Optional[StruggleDynamicsList]:
    """
    Generate 6 struggle-dynamics segments.
    Returns exactly 6 segments: first 3 are 'high-struggle', last 3 are 'peripheral'.

    Returns:
        StruggleDynamicsList, or None on error.
    """
    full_prompt = dynamic_prompt_creator.build_struggle_dynamics_prompt(
        confirmed_user=confirmed_user,
        confirmed_struggle=confirmed_struggle,
        confirmed_solution=confirmed_solution,
        selected_signal=selected_signal,
        user_profile_title=user_profile_title,
        target_location=target_location,
        language_level=language_level,
    )

    result = get_ai_response(
        prompt=full_prompt,
        llm_model=LLM_MODEL,
        output_format=struggle_dynamics_output_format,
        dynamic_thinking_level="medium",
        grounding=True,
        url_context=url_context,
    )

    try:
        parsed = json.loads(result)
        return StruggleDynamicsList.model_validate(parsed)
    except Exception as e:
        print(f"[SD] Failed to parse segment generation result: {e}")
        return None

def verify_segments(
    segments: List[Dict[str, Any]],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Verify struggle dynamics segments.

    Args:
        segments:   List of segment dicts (typically the 3 high-struggle ones).
        signal:     The selected strategic signal context.
        idea:       Business idea context dict.

    Returns:
        Dict with keys: verification_responses, corrected_segments.
    """
    return verify_all_sd_segments(
        segments=segments,
        signal=signal,
        idea=idea,
    )


# ============================================================================
# GENERATE + VERIFY (FULL PIPELINE)
# ============================================================================

def generate_and_verify(
    confirmed_user: str,
    confirmed_struggle: str,
    confirmed_solution: str,
    selected_signal: Union[str, Dict],
    user_profile_title: str,
    target_location: str,
    language_level: str = "STANDARD_BUSINESS",
    url_context: list = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate 6 segments, verify the 3 high-struggle ones, return verified output.

    Returns:
        Dict with:
          - high_struggle_segments: 3 verified/corrected high-struggle segment dicts
          - peripheral_segments:    3 peripheral segment dicts (passed through as-is)
        Or None if generation fails.
    """
    # Step 1: Generate
    sd_result = generate_segments(
        confirmed_user=confirmed_user,
        confirmed_struggle=confirmed_struggle,
        confirmed_solution=confirmed_solution,
        selected_signal=selected_signal,
        user_profile_title=user_profile_title,
        target_location=target_location,
        language_level=language_level,
        url_context=url_context,
    )

    if not sd_result:
        return None

    all_segments = sd_result.struggle_dynamics_segments
    high_struggle_raw = [s.model_dump() for s in all_segments[:3]]
    peripheral_raw = [s.model_dump() for s in all_segments[3:]]

    # Step 2: Verify high-struggle segments
    idea_context = {
        "confirmed_user": confirmed_user,
        "confirmed_struggle": confirmed_struggle,
        "confirmed_solution": confirmed_solution,
        "target_location": target_location,
    }
    signal_dict = selected_signal if isinstance(selected_signal, dict) else None

    verification_result = verify_segments(
        segments=high_struggle_raw,
        signal=signal_dict,
        idea=idea_context,
    )

    return {
        "high_struggle_segments": verification_result["corrected_segments"],
        "peripheral_segments": peripheral_raw,
    }
