"""
Struggle Dynamics controller — generates 6 segments (3 high-struggle + 3 peripheral).
"""
import json
from datetime import datetime
from typing import Union, Dict

from output_formats import StruggleDynamicsList
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
) -> tuple:
    """
    Generate 6 struggle-dynamics segments using the new Struggle Dynamics prompt.
    Returns exactly 6 segments: first 3 are 'high-struggle', last 3 are 'peripheral'.

    Args:
        confirmed_user:     Selected user group (e.g. 'Suburban Parents')
        confirmed_struggle: The core struggle / problem statement
        confirmed_solution: The proposed solution
        selected_signal:    The chosen strategic signal (dict or JSON string)
        user_profile_title: Builder role (e.g. 'startup_founder')
        target_location:    Geographic location (e.g. 'Chicago suburbs, US')
        language_level:     Classification code: PLAIN_ENGLISH | STANDARD_BUSINESS | ADVANCED_TECHNICAL
        url_context:        Optional URLs for additional grounding

    Returns:
        Tuple of (StruggleDynamicsList, metrics_dict) or (None, None) on error
    """
    print("\n" + "="*80)
    print("STEP 1 [Struggle Dynamics]: Generating 6 Segments (high-struggle + peripheral)")
    print("="*80)

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

    print(f"\n👤 Target User:    {confirmed_user}")
    print(f"⚡ Struggle:       {confirmed_struggle[:120]}...")
    print(f"💡 Solution:       {confirmed_solution[:120]}...")
    print(f"📍 Location:       {target_location}")
    print(f"🏗️  Builder:        {user_profile_title}")
    print(f"🗣️  Language:       {language_level}")
    print(f"\n🤖 Calling LLM with grounding and medium thinking (gemini-3.1-pro-preview)...")

    result_tuple = get_ai_response(
        prompt=full_prompt,
        output_format=StruggleDynamicsList,
        grounding=True,
        thinking_level="medium",
        url_context=url_context,
        model="gemini-3-flash-preview"
    )

    if result_tuple and len(result_tuple) == 2:
        result, metrics = result_tuple
    else:
        result, metrics = None, None

    if result:
        high_struggle = [s for s in result.struggle_dynamics_segments if s.validation_tier == "high-struggle"]
        peripheral = [s for s in result.struggle_dynamics_segments if s.validation_tier == "peripheral"]
        print(f"\n✅ Generated {result.total_segments} segments")
        print(f"   🔥 High-Struggle: {len(high_struggle)} segments")
        print(f"   ⚪ Peripheral:    {len(peripheral)} segments")

        if metrics:
            print(f"\n📊 Tokens: {metrics.get('total_tokens', 0):,} "
                  f"(in={metrics.get('input_tokens', 0):,} "
                  f"out={metrics.get('output_tokens', 0):,} "
                  f"think={metrics.get('thinking_tokens', 0):,})")
    else:
        print("❌ Failed to generate struggle dynamics segments")

    return result, metrics
