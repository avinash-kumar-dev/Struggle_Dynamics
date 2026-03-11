"""
Struggle Dynamics controller — generates segments and market sizings.

Public API
----------
generate_struggle_dynamics_segments(...)  -> StruggleDynamicsList | None
generate_market_sizings(...)              -> list[EnhancedMarketSizing | None]
market_sizings_to_dicts(...)              -> list[dict]
"""
import json
import asyncio
from datetime import datetime
from typing import Union, Dict, List, Any, Optional

from output_formats import StruggleDynamicsList, EnhancedMarketSizing
from llm_call import get_ai_response
import prompts


# ============================================================================
# LANGUAGE DIRECTIVE MAP  (also lives in prompts.py for reference)
# ============================================================================
LANGUAGE_DIRECTIVE_MAP = {
    "PLAIN_ENGLISH": """
# Communication Style: "The Mentor"
**Target:** Solopreneurs, first-time founders, or users typing casually.

**The Vibe:** Encouraging but entirely objective. You use the Socratic method to guide them to the flaw in their own idea.

**The Rule:** Ask one clear question at a time. Use simple analogies to explain complex concepts (like CAC or Churn) if you introduce them. Never make them feel stupid.

**Critique Style:** Focus on user friction and logical gaps.
""",
    "STANDARD_BUSINESS": """
# Communication Style: "The Elite Operator"
**Target:** Startup Teams, experienced operators, and users using standard tech terms.

**The Vibe:** Fast-paced, pragmatic, tactical, and slightly urgent. Think of a Y Combinator partner or a technical co-founder whiteboarding at 2:00 AM.

**The Rule:** Be direct and cut the fluff. Challenge their assumptions aggressively. Speak in standard startup shorthand (PMF, MVP, CAC, LTV, Burn) without explaining what the acronyms mean.

**Critique Style:** Attack the mechanics, distribution, and unit economics.
""",
    "ADVANCED_TECHNICAL": """
# Communication Style: "The Board Member"
**Target:** VCs, Startup Studios, or highly technical/elite founders.

**The Vibe:** Cold, high-bandwidth, intensely analytical, and purely objective. Think of an elite strategist or lead investor reviewing a thesis.

**The Rule:** Zero padding. Deliver high-density information. Focus purely on systemic risks, market dynamics, network effects, and capital efficiency.

**Critique Style:** Assess the idea purely on risk and scale.
""",
}


def generate_struggle_dynamics_segments(
    confirmed_user: str,
    confirmed_struggle: str,
    confirmed_solution: str,
    selected_signal: Union[str, Dict],
    user_profile_title: str,
    target_location: str,
    language_level: str = "STANDARD_BUSINESS",
    url_context: list = None
) -> Optional["StruggleDynamicsList"]:
    """
    Generate 6 struggle-dynamics segments.
    Returns exactly 6 segments: first 3 are 'high-struggle', last 3 are 'peripheral'.

    Returns:
        StruggleDynamicsList, or None on error.
    """
    # Expand language code → full directive string
    language_directive_block = LANGUAGE_DIRECTIVE_MAP.get(
        language_level,
        LANGUAGE_DIRECTIVE_MAP["STANDARD_BUSINESS"]
    )

    # Serialise signal to string if dict
    if isinstance(selected_signal, dict):
        selected_signal_str = json.dumps(selected_signal, indent=2)
    else:
        selected_signal_str = str(selected_signal)

    full_prompt = prompts.STRUGGLE_DYNAMICS_SEGMENT_PROMPT.format(
        current_date=datetime.now().strftime("%B %d, %Y"),
        confirmed_user=confirmed_user,
        confirmed_struggle=confirmed_struggle,
        confirmed_solution=confirmed_solution,
        selected_signal_json_or_text=selected_signal_str,
        user_profile_title=user_profile_title,
        target_location=target_location,
        language_directive_block=language_directive_block
    )

    result = get_ai_response(
        prompt=full_prompt,
        output_format=StruggleDynamicsList,
        grounding=True,
        thinking_level="medium",
        url_context=url_context,
        model="gemini-3-flash-preview"
    )

    return result


# ============================================================================
# MARKET SIZING
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

    Returns:
        List of EnhancedMarketSizing objects (None for failed calls).
    """
    from llm_call import batch_ai_responses

    jtbd_str = json.dumps(jtbd) if isinstance(jtbd, dict) else (jtbd or "")
    idea_str = json.dumps(idea) if isinstance(idea, dict) else (idea or "")
    current_date = datetime.now().strftime("%B %d, %Y")

    target_segments = segments[:max_segments]

    prompts_list: List[str] = []
    for seg in target_segments:
        p = prompts.MARKET_SIZING_PROMPT.format(
            jtbd=jtbd_str,
            idea=idea_str,
            segment_name=seg.get("segment_name", ""),
            segment_description=seg.get("description", ""),
            location=location,
            current_date=current_date,
        )
        prompts_list.append(p)

    results = asyncio.run(
        batch_ai_responses(
            prompts=prompts_list,
            output_format=EnhancedMarketSizing,
            grounding=True,
            thinking_level="medium",
        )
    )

    return results


def market_sizings_to_dicts(
    results: List[Optional[EnhancedMarketSizing]],
) -> List[Dict[str, Any]]:
    """
    Serialise EnhancedMarketSizing objects to plain dicts.

    Returns:
        List of dicts (None for failed calls).
    """
    dicts: List[Any] = []

    for result in results:
        if result is None:
            dicts.append(None)
            continue
        dicts.append(json.loads(result.model_dump_json()))

    return dicts
