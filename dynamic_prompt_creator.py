"""
Dynamic prompt builder for the Struggle Dynamics module.

All prompt construction logic lives here.
Controllers call these functions to get fully assembled prompt strings.

Public API
----------
build_struggle_dynamics_prompt(...)       -> str
build_market_sizing_prompt(...)           -> str
build_sd_verification_prompt(...)         -> str
build_market_verification_prompt(...)     -> str
"""
import json
from datetime import datetime
from typing import Union, Dict, Any, Optional

import prompts


# ============================================================================
# HELPERS
# ============================================================================

def _resolve_language_directive(language_level: str) -> str:
    """Return the full language-directive block for a given language-level code."""
    return prompts.LANGUAGE_DIRECTIVE_MAP.get(
        language_level,
        prompts.LANGUAGE_DIRECTIVE_MAP["STANDARD_BUSINESS"]
    )


def _signal_to_str(selected_signal: Union[str, Dict, Any]) -> str:
    """Serialise a signal value (dict or string) to a string."""
    if isinstance(selected_signal, dict):
        return json.dumps(selected_signal, indent=2)
    return str(selected_signal)


# ============================================================================
# PROMPT BUILDERS
# ============================================================================

def build_struggle_dynamics_prompt(
    confirmed_user: str,
    confirmed_struggle: str,
    confirmed_solution: str,
    selected_signal: Union[str, Dict],
    user_profile_title: str,
    target_location: str,
    language_level: str = "STANDARD_BUSINESS",
) -> str:
    """
    Assemble and return the fully formatted Struggle Dynamics segment prompt.

    Args:
        confirmed_user:      The validated target user description.
        confirmed_struggle:  The validated core struggle.
        confirmed_solution:  The validated proposed solution.
        selected_signal:     The strategic signal (dict or plain string).
        user_profile_title:  Builder profile label (e.g. "Indie Hacker").
        target_location:     Geographic context for the analysis.
        language_level:      One of "PLAIN_ENGLISH", "STANDARD_BUSINESS",
                             "ADVANCED_TECHNICAL". Defaults to STANDARD_BUSINESS.

    Returns:
        A fully formatted prompt string ready to be sent to the LLM.
    """
    language_directive_block = _resolve_language_directive(language_level)
    selected_signal_str = _signal_to_str(selected_signal)

    return prompts.STRUGGLE_DYNAMICS_SEGMENT_PROMPT.format(
        current_date=datetime.now().strftime("%B %d, %Y"),
        confirmed_user=confirmed_user,
        confirmed_struggle=confirmed_struggle,
        confirmed_solution=confirmed_solution,
        selected_signal_json_or_text=selected_signal_str,
        user_profile_title=user_profile_title,
        target_location=target_location,
        language_directive_block=language_directive_block,
    )


def build_market_sizing_prompt(
    segment: Dict[str, Any],
    jtbd: Any,
    idea: Any,
    location: str,
) -> str:
    """
    Assemble and return the fully formatted Market Sizing prompt for one segment.

    Args:
        segment:   A segment dict containing at least 'segment_name' and 'description'.
        jtbd:      Job-To-Be-Done context (dict or string).
        idea:      The product idea (dict or string).
        location:  Target market location string.

    Returns:
        A fully formatted prompt string ready to be sent to the LLM.
    """
    jtbd_str = json.dumps(jtbd) if isinstance(jtbd, dict) else (jtbd or "")
    idea_str = json.dumps(idea) if isinstance(idea, dict) else (idea or "")

    return prompts.MARKET_SIZING_PROMPT.format(
        jtbd=jtbd_str,
        idea=idea_str,
        segment_name=segment.get("segment_name", ""),
        segment_description=segment.get("description", ""),
        location=location,
        current_date=datetime.now().strftime("%B %d, %Y"),
    )



# ============================================================================
# VERIFICATION PROMPT BUILDERS
# ============================================================================

# Pre-formatted base prompts (date is baked in at import time)
_SD_VERIFICATION_BASE = prompts.STRUGGLE_DYNAMICS_VERIFICATION_PROMPT.format(
    current_date=datetime.now().strftime("%B %d, %Y")
)
_MARKET_VERIFICATION_TEMPLATE = prompts.MARKET_VERIFICATION_SYSTEM_PROMPT

# Fields verified in each SD segment
SD_BASE_FIELDS = [
    "behavioral_evidence",
    "pain_intensity",
    "current_solutions",
    "segment_accessibility",
]


def build_sd_verification_prompt(
    segment: Dict[str, Any],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> str:
    """
    Assemble the verification prompt for one Struggle Dynamics segment.

    Args:
        segment: A segment dict (must contain segment_name, validation_data, etc.).
        signal:  Optional strategic signal context dict.
        idea:    Optional business idea context dict.

    Returns:
        A fully formatted prompt string ready to be sent to the LLM.
    """
    segment_name = segment.get("segment_name", "Unknown")
    validation_data = segment.get("validation_data", {})

    parts = [
        _SD_VERIFICATION_BASE,
        "",
        "=" * 80,
        "",
        f"SEGMENT: {segment_name}",
        f"ACUTENESS RATIONALE: {segment.get('acuteness_rationale', 'N/A')}",
        "",
    ]

    if signal or idea:
        parts.append("BUSINESS CONTEXT:")
        if idea:
            parts.append(f"  Problem: {idea.get('problem', idea.get('confirmed_struggle', 'N/A'))}")
            parts.append(f"  Solution: {idea.get('solution', idea.get('confirmed_solution', 'N/A'))}")
            parts.append(f"  Target User: {idea.get('confirmed_user', idea.get('target_user', 'N/A'))}")
            parts.append(f"  Location: {idea.get('target_location', idea.get('location', 'N/A'))}")
        if signal:
            parts.append(f"  Signal: {json.dumps(signal)[:300]}")
        parts.append("")

    parts.append("CLAIMS TO VERIFY:")
    parts.append("")

    for i, field_name in enumerate(SD_BASE_FIELDS, 1):
        if field_name in validation_data:
            fd = validation_data[field_name]
            value = fd.get("value", "") if isinstance(fd, dict) else str(fd)
            source_urls = fd.get("source_urls", []) if isinstance(fd, dict) else []
            if value:
                parts.append(f"{i}. {field_name.replace('_', ' ').title()}: '{value}'")
                if source_urls:
                    parts.append(f"   Sources: {source_urls}")
                parts.append("")

    return "\n".join(parts)


def build_market_verification_prompt(
    market_sizing: Dict[str, Any],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> str:
    """
    Assemble the verification prompt for one market sizing dict.

    Three data sections are injected into the template:
      {segment_info}      — segment name + location
      {business_context}  — problem, target user, JTBD
      {claims_to_verify}  — population data + pricing data
    """
    segment_name = market_sizing.get("segment_name", "Unknown")
    location = market_sizing.get("location", "Unknown")
    population_data = market_sizing.get("struggle_aware_population", {})
    pricing_scenarios = market_sizing.get("pricing_scenarios", [])

    # ── 1. Segment info ──────────────────────────────────────────────────
    segment_info = f"Segment: {segment_name}\nLocation: {location}"

    # ── 2. Business context ───────────────────────────────────────────────
    ctx_parts = []
    if idea:
        ctx_parts.append(f"Problem: {idea.get('problem', idea.get('confirmed_struggle', 'N/A'))}")
        ctx_parts.append(f"Target User: {idea.get('target_user', idea.get('confirmed_user', 'N/A'))}")
    if jtbd:
        narrative = jtbd.get("narrative", "N/A")
        if len(narrative) > 200:
            narrative = narrative[:200] + "..."
        ctx_parts.append(f"JTBD: {narrative}")
    business_context = "\n".join(ctx_parts) if ctx_parts else "N/A"

    # ── 3. Claims to verify ───────────────────────────────────────────────
    claims = []
    claim_num = 1

    # Population claims
    if population_data:
        claims.append("=== POPULATION DATA ===")
        claims.append("")

        total_pop = population_data.get("total_population")
        pop_source = population_data.get("population_source", "N/A")
        pop_source_urls = population_data.get("population_source_urls", [])
        if total_pop:
            claims.append(f"{claim_num}. Total Population: {total_pop:,} in {location}")
            claims.append(f"   Source: {pop_source}")
            if pop_source_urls:
                claims.append(f"   Claimed Source URLs: {', '.join(pop_source_urls)}")
            claims.append("")
            claim_num += 1

        prevalence = population_data.get("prevalence_rate")
        prev_source = population_data.get("prevalence_source", "N/A")
        prev_source_urls = population_data.get("prevalence_source_urls", [])
        if prevalence is not None:
            claims.append(f"{claim_num}. Prevalence Rate: {prevalence * 100:.1f}% (people experiencing this struggle)")
            claims.append(f"   Source: {prev_source}")
            if prev_source_urls:
                claims.append(f"   Claimed Source URLs: {', '.join(prev_source_urls)}")
            claims.append("")
            claim_num += 1

        struggle_count = population_data.get("struggle_aware_count")
        calc_logic = population_data.get("calculation_logic", "N/A")
        if struggle_count:
            claims.append(f"{claim_num}. Struggle-Aware Count: {struggle_count:,}")
            claims.append(f"   Calculation: {calc_logic}")
            claims.append("")
            claim_num += 1

    # Pricing claims
    if pricing_scenarios:
        claims.append("=== PRICING DATA ===")
        claims.append("")
        for i, scenario in enumerate(pricing_scenarios, 1):
            tier = scenario.get("tier", "Unknown")
            annual_price = scenario.get("annual_price")
            claims.append(f"SCENARIO {i}: {tier}")
            if annual_price:
                claims.append(f"   Annual Price: ${annual_price:,}")
                rationale = scenario.get("pricing_rationale", "")
                if len(rationale) > 100:
                    rationale = rationale[:100] + "..."
                claims.append(f"   Rationale: {rationale}")

            pricing_source_urls = scenario.get("pricing_source_urls", [])
            if pricing_source_urls:
                claims.append(f"   Claimed Pricing Source URLs: {', '.join(pricing_source_urls)}")

            comparables = scenario.get("comparable_solutions", [])
            if comparables:
                claims.append("   Comparable Solutions:")
                for comp in comparables:
                    line = (
                        f"     - {comp.get('solution_name', 'Unknown')}: "
                        f"{comp.get('price', 'Unknown')} "
                        f"(Source: {comp.get('source', 'N/A')})"
                    )
                    url = comp.get("source_url", "")
                    if url:
                        line += f" | URL: {url}"
                    claims.append(line)
            claims.append("")

    claims_to_verify = "\n".join(claims) if claims else "No claims provided."

    # ── Format the template ───────────────────────────────────────────────
    return _MARKET_VERIFICATION_TEMPLATE.format(
        current_date=datetime.now().strftime("%B %d, %Y"),
        segment_info=segment_info,
        business_context=business_context,
        claims_to_verify=claims_to_verify,
    )
