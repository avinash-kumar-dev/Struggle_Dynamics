"""
Struggle Dynamics controller — orchestrates the full pipeline.

Delegates to:
  - segment_controller:        segment generation + verification
  - market_sizing_controller:  market sizing generation + verification

Public API
----------
run_full_pipeline(...)  -> dict   (segments + market sizing, generated & verified)
"""
from typing import Union, Dict, List, Any, Optional

import segment_controller
import market_sizing_controller


def run_full_pipeline(
    confirmed_user: str,
    confirmed_struggle: str,
    confirmed_solution: str,
    selected_signal: Union[str, Dict],
    user_profile_title: str,
    target_location: str,
    language_level: str = "STANDARD_BUSINESS",
    url_context: list = None,
    max_market_segments: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    Run the complete Struggle Dynamics pipeline:
      1. Generate 6 segments (3 high-struggle + 3 peripheral)
      2. Verify the 3 high-struggle segments
      3. Generate market sizing for corrected high-struggle segments
      4. Verify market sizing data

    Returns:
        Dict with all results, or None if segment generation fails.
    """
    # ── Step 1 + 2: Segments (generate + verify) ──────────────────────────
    seg_result = segment_controller.generate_and_verify(
        confirmed_user=confirmed_user,
        confirmed_struggle=confirmed_struggle,
        confirmed_solution=confirmed_solution,
        selected_signal=selected_signal,
        user_profile_title=user_profile_title,
        target_location=target_location,
        language_level=language_level,
        url_context=url_context,
    )

    if not seg_result:
        return None

    # ── Step 3 + 4: Market Sizing (generate + verify) ─────────────────────
    corrected_high_struggle = seg_result["high_struggle_segments"]

    idea_for_market = {
        "problem": confirmed_struggle,
        "solution": confirmed_solution,
        "target_user": confirmed_user,
    }
    signal_dict = selected_signal if isinstance(selected_signal, dict) else None

    ms_result = market_sizing_controller.generate_and_verify(
        segments=corrected_high_struggle,
        jtbd=signal_dict,
        idea=idea_for_market,
        location=target_location,
        max_segments=max_market_segments,
    )

    return {
        # Segment outputs
        "high_struggle_segments": seg_result["high_struggle_segments"],
        "peripheral_segments": seg_result["peripheral_segments"],
        "all_segments": seg_result["high_struggle_segments"] + seg_result["peripheral_segments"],
        # Market sizing outputs
        "corrected_market_sizings": ms_result["corrected_market_sizings"],
    }

