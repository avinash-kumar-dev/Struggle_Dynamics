"""
Market Sizing Verification for the Struggle Dynamics module.

Verifies population data (total_population, prevalence_rate, struggle_aware_count)
and pricing data (annual_price per tier) produced by market_sizing.py.

Public API
----------
verify_all_market_sizings(market_sizings, jtbd, idea, batch_size) -> dict
"""

import asyncio
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

from output_formats import (
    MarketFieldVerificationResult,
    MarketSizingVerificationResult,
    MarketVerificationSummary,
    FieldVerificationData,
    MarketVerificationLLMOutput,
)
from prompts import MARKET_VERIFICATION_SYSTEM_PROMPT

_MARKET_VERIFICATION_PROMPT_FORMATTED = MARKET_VERIFICATION_SYSTEM_PROMPT.format(
    current_date=datetime.now().strftime("%B %d, %Y")
)


# ============================================================================
# URL VALIDATION
# ============================================================================

async def validate_urls_async(urls: List[str], timeout: int = 5) -> List[str]:
    """Validate all URLs concurrently; return only accessible ones."""
    if not urls:
        return []
    _headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }

    def _check(url: str) -> Optional[str]:
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True, headers=_headers)
            if r.status_code == 405 or r.status_code >= 400:
                r = requests.get(url, timeout=timeout, allow_redirects=True, headers=_headers, stream=True)
                r.close()
            return url if r.status_code < 400 else None
        except Exception:
            return None

    results = await asyncio.gather(*[asyncio.to_thread(_check, url) for url in urls])
    return [u for u in results if u]


# ============================================================================
# PROMPT BUILDER
# ============================================================================

def build_market_verification_prompt(
    market_sizing: Dict[str, Any],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> str:
    """Build the full verification prompt for one EnhancedMarketSizing dict."""
    segment_name   = market_sizing.get("segment_name", "Unknown")
    location       = market_sizing.get("location", "Unknown")
    population_data = market_sizing.get("struggle_aware_population", {})
    pricing_scenarios = market_sizing.get("pricing_scenarios", [])

    parts = [
        _MARKET_VERIFICATION_PROMPT_FORMATTED,
        "",
        "=" * 80,
        "",
        f"SEGMENT: {segment_name}",
        f"LOCATION: {location}",
        "",
    ]

    if idea or jtbd:
        parts.append("BUSINESS CONTEXT:")
        if idea:
            parts.append(f"Problem: {idea.get('problem', idea.get('confirmed_struggle', 'N/A'))}")
            parts.append(f"Target User: {idea.get('target_user', idea.get('confirmed_user', 'N/A'))}")
        if jtbd:
            narrative = jtbd.get("narrative", "N/A")
            if len(narrative) > 200:
                narrative = narrative[:200] + "..."
            parts.append(f"JTBD: {narrative}")
        parts.append("")

    parts.extend(["CLAIMS TO VERIFY:", "", "=== POPULATION DATA ===", ""])

    claim_num = 1
    if population_data:
        total_pop        = population_data.get("total_population")
        pop_source       = population_data.get("population_source", "N/A")
        pop_source_urls  = population_data.get("population_source_urls", [])
        if total_pop:
            parts.append(f"{claim_num}. Total Population: {total_pop:,} in {location}")
            parts.append(f"   Source: {pop_source}")
            if pop_source_urls:
                parts.append(f"   Claimed Source URLs: {', '.join(pop_source_urls)}")
            parts.append("")
            claim_num += 1

        prevalence       = population_data.get("prevalence_rate")
        prev_source      = population_data.get("prevalence_source", "N/A")
        prev_source_urls = population_data.get("prevalence_source_urls", [])
        if prevalence is not None:
            parts.append(f"{claim_num}. Prevalence Rate: {prevalence * 100:.1f}% (people experiencing this struggle)")
            parts.append(f"   Source: {prev_source}")
            if prev_source_urls:
                parts.append(f"   Claimed Source URLs: {', '.join(prev_source_urls)}")
            parts.append("")
            claim_num += 1

        struggle_count = population_data.get("struggle_aware_count")
        calc_logic     = population_data.get("calculation_logic", "N/A")
        if struggle_count:
            parts.append(f"{claim_num}. Struggle-Aware Count: {struggle_count:,}")
            parts.append(f"   Calculation: {calc_logic}")
            parts.append("")
            claim_num += 1

    if pricing_scenarios:
        parts.extend(["=== PRICING DATA ===", ""])
        for i, scenario in enumerate(pricing_scenarios, 1):
            tier         = scenario.get("tier", "Unknown")
            annual_price = scenario.get("annual_price")
            parts.append(f"SCENARIO {i}: {tier}")
            if annual_price:
                parts.append(f"   Annual Price: ${annual_price:,}")
                rationale = scenario.get("pricing_rationale", "")
                if len(rationale) > 100:
                    rationale = rationale[:100] + "..."
                parts.append(f"   Rationale: {rationale}")

            pricing_source_urls = scenario.get("pricing_source_urls", [])
            if pricing_source_urls:
                parts.append(f"   Claimed Pricing Source URLs: {', '.join(pricing_source_urls)}")

            comparables = scenario.get("comparable_solutions", [])
            if comparables:
                parts.append("   Comparable Solutions:")
                for comp in comparables:
                    line = (
                        f"     - {comp.get('solution_name', 'Unknown')}: "
                        f"{comp.get('price', 'Unknown')} "
                        f"(Source: {comp.get('source', 'N/A')})"
                    )
                    url = comp.get("source_url", "")
                    if url:
                        line += f" | URL: {url}"
                    parts.append(line)
            parts.append("")

    return "\n".join(parts)


# ============================================================================
# RESPONSE PARSER
# ============================================================================

async def parse_market_verification_response(
    llm_output: MarketVerificationLLMOutput,
    market_sizing: Dict[str, Any],
) -> MarketSizingVerificationResult:
    """Translate LLM output into a MarketSizingVerificationResult."""
    segment_name = market_sizing.get("segment_name", "Unknown")
    location     = market_sizing.get("location", "Unknown")
    field_results: List[MarketFieldVerificationResult] = []

    for fv in llm_output.fields:
        field_name   = fv.field_name
        pricing_tier = fv.pricing_tier

        claimed_value = ""
        source        = ""
        source_urls: List[str] = []

        if field_name in ("total_population", "prevalence_rate", "struggle_aware_count"):
            pop = market_sizing.get("struggle_aware_population", {})
            if field_name == "total_population":
                claimed_value = f"{pop.get('total_population', 0):,}"
                source        = pop.get("population_source", "")
                source_urls   = pop.get("population_source_urls", [])
            elif field_name == "prevalence_rate":
                claimed_value = f"{pop.get('prevalence_rate', 0) * 100:.1f}%"
                source        = pop.get("prevalence_source", "")
                source_urls   = pop.get("prevalence_source_urls", [])
            else:
                claimed_value = f"{pop.get('struggle_aware_count', 0):,}"
                source        = pop.get("calculation_logic", "")
                source_urls   = (
                    pop.get("population_source_urls", []) +
                    pop.get("prevalence_source_urls", [])
                )
        elif pricing_tier:
            for scenario in market_sizing.get("pricing_scenarios", []):
                if scenario.get("tier") == pricing_tier:
                    claimed_value = f"${scenario.get('annual_price', 0):,}"
                    comp          = (scenario.get("comparable_solutions") or [{}])[0]
                    source        = comp.get("source", "")
                    source_urls   = list(scenario.get("pricing_source_urls", []))
                    for c in scenario.get("comparable_solutions", []):
                        u = c.get("source_url", "")
                        if u:
                            source_urls.append(u)
                    break

        verified_value           = fv.verified_value
        confidence_score         = fv.confidence_score
        discrepancies            = fv.discrepancies
        correction_needed        = fv.correction_needed
        corrected_value          = fv.corrected_value
        verification_sources_raw = fv.verification_sources
        verified_source_urls     = fv.verified_source_urls

        verification_sources_validated = (
            await validate_urls_async(verification_sources_raw) if verification_sources_raw else []
        )

        if verified_value == "Unable to verify" or confidence_score == 0:
            status = "unable_to_verify"
        elif correction_needed:
            status = "corrected"
        else:
            status = "verified"

        field_results.append(MarketFieldVerificationResult(
            field_name=field_name,
            pricing_tier=pricing_tier,
            claimed_value=claimed_value,
            source=source,
            source_urls=source_urls,
            verified_value=verified_value,
            confidence_score=confidence_score,
            verification_status=status,
            discrepancies=discrepancies,
            correction_needed=correction_needed,
            corrected_value=corrected_value,
            verification_sources_claimed=verification_sources_raw,
            verified_source_urls=verified_source_urls,
            verification_sources=verification_sources_validated,
        ))

    avg_confidence = (
        sum(f.confidence_score for f in field_results) / len(field_results)
        if field_results else 0.0
    )
    verified_count  = sum(1 for f in field_results if f.verification_status == "verified")
    corrected_count = sum(1 for f in field_results if f.verification_status == "corrected")
    unable_count    = sum(1 for f in field_results if f.verification_status == "unable_to_verify")

    quality = (
        "high" if avg_confidence >= 80 and corrected_count <= 1
        else "medium" if avg_confidence >= 60
        else "low"
    )

    return MarketSizingVerificationResult(
        segment_name=segment_name,
        location=location,
        field_results=field_results,
        overall_quality=quality,
        average_confidence=avg_confidence,
        fields_verified=verified_count,
        fields_corrected=corrected_count,
        fields_unable_to_verify=unable_count,
        verification_timestamp=datetime.now().isoformat(),
    )


# ============================================================================
# ASYNC VERIFY ONE SEGMENT
# ============================================================================

async def verify_market_sizing_async(
    market_sizing: Dict[str, Any],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Optional[MarketSizingVerificationResult]:
    """Verify one market sizing dict asynchronously."""
    from llm_call import get_ai_response_async

    segment_name = market_sizing.get("segment_name", "Unknown")
    prompt = build_market_verification_prompt(market_sizing, jtbd, idea)

    llm_output = await get_ai_response_async(
        prompt=prompt,
        output_format=MarketVerificationLLMOutput,
        grounding=True,
        thinking_level="medium",
    )

    if not llm_output:
        print(f"   ❌ {segment_name}: Verification failed")
        return None

    return await parse_market_verification_response(llm_output, market_sizing)


# ============================================================================
# BATCH VERIFY (ASYNC IMPLEMENTATION)
# ============================================================================

async def verify_all_market_sizings_async(
    market_sizings: List[Dict[str, Any]],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
    batch_size: int = 3,
) -> Dict[str, Any]:
    """Verify all market sizings in parallel batches."""
    verification_results: List[MarketSizingVerificationResult] = []

    for i in range(0, len(market_sizings), batch_size):
        batch = [ms for ms in market_sizings[i:i + batch_size] if ms]


        tasks = [
            verify_market_sizing_async(ms, jtbd=jtbd, idea=idea)
            for ms in batch
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
                print(f"   ❌ Verification error: {result}")
                continue
            if result:
                verification_results.append(result)

    summary           = _generate_summary(verification_results)
    corrected_sizings = _apply_corrections(market_sizings, verification_results)

    return {
        "verification_results": verification_results,
        "summary": summary,
        "corrected_market_sizings": corrected_sizings,
    }


# ============================================================================
# SYNC WRAPPER
# ============================================================================

def verify_all_market_sizings(
    market_sizings: List[Dict[str, Any]],
    jtbd: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
    batch_size: int = 3,
) -> Dict[str, Any]:
    """Synchronous wrapper around verify_all_market_sizings_async."""
    return asyncio.run(verify_all_market_sizings_async(market_sizings, jtbd, idea, batch_size))


# ============================================================================
# SUMMARY + CORRECTIONS
# ============================================================================

def _generate_summary(results: List[MarketSizingVerificationResult]) -> MarketVerificationSummary:
    total_segments = len(results)
    avg_confidence = (
        sum(r.average_confidence for r in results) / total_segments
        if total_segments else 0.0
    )
    return MarketVerificationSummary(
        total_segments_verified=total_segments,
        total_fields_verified=sum(len(r.field_results) for r in results),
        verified_accurate=sum(r.fields_verified for r in results),
        verified_corrected=sum(r.fields_corrected for r in results),
        unable_to_verify=sum(r.fields_unable_to_verify for r in results),
        average_confidence=avg_confidence,
        high_quality_segments=sum(1 for r in results if r.overall_quality == "high"),
        medium_quality_segments=sum(1 for r in results if r.overall_quality == "medium"),
        low_quality_segments=sum(1 for r in results if r.overall_quality == "low"),
    )


def _apply_corrections(
    original_sizings: List[Dict[str, Any]],
    verification_results: List[MarketSizingVerificationResult],
) -> List[Dict[str, Any]]:
    """Apply verified corrections back onto the original market sizing dicts."""
    vmap = {r.segment_name: r for r in verification_results}
    corrected: List[Any] = []

    for sizing in original_sizings:
        if not sizing:
            corrected.append(None)
            continue

        seg_name = sizing.get("segment_name", "")
        cs       = sizing.copy()

        if seg_name in vmap:
            vr  = vmap[seg_name]
            pop = cs.get("struggle_aware_population", {})

            for fr in vr.field_results:
                updated = (
                    fr.corrected_value
                    if fr.correction_needed and fr.corrected_value
                    else fr.verified_value
                )
                if fr.field_name == "total_population":
                    try:
                        pop["total_population"] = int(updated.replace(",", "").split()[0])
                    except Exception:
                        pass
                elif fr.field_name == "prevalence_rate":
                    try:
                        pop["prevalence_rate"] = float(updated.replace("%", "").split()[0]) / 100
                    except Exception:
                        pass
                elif fr.field_name == "struggle_aware_count":
                    try:
                        pop["struggle_aware_count"] = int(updated.replace(",", "").split()[0])
                    except Exception:
                        pass

                if fr.field_name in ("total_population", "prevalence_rate", "struggle_aware_count"):
                    pop[f"{fr.field_name}_verified_sources"]    = fr.verification_sources
                    pop[f"{fr.field_name}_verified_source_urls"] = fr.verified_source_urls
                    pop[f"{fr.field_name}_verification_status"] = fr.verification_status
                    pop[f"{fr.field_name}_confidence"]          = fr.confidence_score

            cs["_market_verification_metadata"] = {
                "verified":              True,
                "verification_timestamp": vr.verification_timestamp,
                "overall_quality":       vr.overall_quality,
                "confidence_avg":        vr.average_confidence,
                "fields_verified":       vr.fields_verified,
                "fields_corrected":      vr.fields_corrected,
                "fields_unable_to_verify": vr.fields_unable_to_verify,
            }
        else:
            cs["_market_verification_metadata"] = {
                "verified": False,
                "reason":   "Not selected for verification",
            }

        corrected.append(cs)

    return corrected
