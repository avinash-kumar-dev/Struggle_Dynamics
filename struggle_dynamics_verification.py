"""
Struggle Dynamics Verification Pipeline
Verifies the 6-segment output from the Struggle Dynamics phase.

Schema differences vs. segment_verification.py:
  - validation_tier   ("high-struggle" / "peripheral")    instead of priority_level
  - acuteness_rationale                                    instead of priority_rationale
"""

import json
import asyncio
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from output_formats import FieldVerificationResult, SDSegmentVerificationResult, SDVerificationSummary
from prompts import STRUGGLE_DYNAMICS_VERIFICATION_PROMPT

_VERIFICATION_PROMPT_FORMATTED = STRUGGLE_DYNAMICS_VERIFICATION_PROMPT.format(
    current_date=datetime.now().strftime("%B %d, %Y")
)


# ==================== URL VALIDATION ====================

async def validate_urls_async(urls: List[str], timeout: int = 5) -> List[str]:
    """Validate all URLs concurrently; return only accessible ones."""
    if not urls:
        return []
    _headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
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


# ==================== FIELDS & SCHEMAS ====================

BASE_FIELDS = [
    'behavioral_evidence',
    'pain_intensity',
    'current_solutions',
    'segment_accessibility',
]


# --- Response schema (module-level: defined once, not recreated per call) ---
class _FieldVerification(BaseModel):
    verified_value: str
    confidence_score: int
    discrepancies: List[str] = Field(default_factory=list)
    correction_needed: bool
    corrected_value: str = ""
    verification_sources: List[str] = Field(default_factory=list)


class _SDVerificationResponse(BaseModel):
    behavioral_evidence: _FieldVerification
    pain_intensity: _FieldVerification
    current_solutions: _FieldVerification
    segment_accessibility: _FieldVerification
    updated_acuteness_rationale: str


# ==================== PROMPT BUILDING ====================

def build_sd_verification_prompt(
    segment: Dict[str, Any],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None
) -> str:
    """Build the verification prompt for one Struggle Dynamics segment."""
    segment_name = segment.get('segment_name', 'Unknown')
    validation_data = segment.get('validation_data', {})

    parts = [
        _VERIFICATION_PROMPT_FORMATTED,
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

    for i, field_name in enumerate(BASE_FIELDS, 1):
        if field_name in validation_data:
            fd = validation_data[field_name]
            value = fd.get('value', '') if isinstance(fd, dict) else str(fd)
            source_urls = fd.get('source_urls', []) if isinstance(fd, dict) else []
            if value:
                parts.append(f"{i}. {field_name.replace('_', ' ').title()}: '{value}'")
                if source_urls:
                    parts.append(f"   Sources: {source_urls}")
                parts.append("")

    return "\n".join(parts)


# ==================== PARSING ====================

async def parse_sd_verification_response(
    response: _SDVerificationResponse,
    segment: Dict[str, Any]
) -> SDSegmentVerificationResult:
    """Parse (typed) LLM verification response into SDSegmentVerificationResult."""
    segment_name    = segment.get('segment_name', 'Unknown')
    validation_tier = segment.get('validation_tier', 'peripheral')
    validation_data = segment.get('validation_data', {})
    field_results   = []

    for field_name in BASE_FIELDS:
        if field_name not in validation_data:
            continue
        fd = validation_data[field_name]
        claimed_value = fd.get('value', '') if isinstance(fd, dict) else str(fd)
        source_urls   = fd.get('source_urls', []) if isinstance(fd, dict) else []

        fv = getattr(response, field_name)  # typed _FieldVerification — no .get() needed

        verification_sources_validated = (
            await validate_urls_async(fv.verification_sources)
            if fv.verification_sources else []
        )

        if fv.verified_value == 'Unable to verify' or fv.confidence_score == 0:
            status = 'unable_to_verify'
        elif fv.correction_needed:
            status = 'corrected'
        else:
            status = 'verified'

        field_results.append(FieldVerificationResult(
            field_name=field_name,
            claimed_value=claimed_value,
            source_urls=source_urls,
            verified_value=fv.verified_value,
            confidence_score=fv.confidence_score,
            verification_status=status,
            discrepancies=fv.discrepancies,
            correction_needed=fv.correction_needed,
            corrected_value=fv.corrected_value,
            verification_sources_claimed=fv.verification_sources,
            verification_sources=verification_sources_validated,
        ))

    avg_confidence  = (
        sum(f.confidence_score for f in field_results) / len(field_results)
        if field_results else 0.0
    )
    verified_count  = sum(1 for f in field_results if f.verification_status == 'verified')
    corrected_count = sum(1 for f in field_results if f.verification_status == 'corrected')
    unable_count    = sum(1 for f in field_results if f.verification_status == 'unable_to_verify')

    quality = (
        'high'   if avg_confidence >= 80 and corrected_count <= 1
        else 'medium' if avg_confidence >= 60
        else 'low'
    )

    acuteness_original = segment.get('acuteness_rationale', '')
    acuteness_updated  = response.updated_acuteness_rationale or acuteness_original

    return SDSegmentVerificationResult(
        segment_name=segment_name,
        validation_tier=validation_tier,
        field_results=field_results,
        overall_segment_quality=quality,
        segment_confidence_avg=avg_confidence,
        fields_verified=verified_count,
        fields_corrected=corrected_count,
        fields_unable_to_verify=unable_count,
        acuteness_rationale_original=acuteness_original,
        acuteness_rationale_updated=acuteness_updated,
        verification_timestamp=datetime.now().isoformat(),
    )


# ==================== ASYNC VERIFY ONE SEGMENT ====================

async def verify_sd_segment_async(
    segment: Dict[str, Any],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None
):
    """Verify one Struggle Dynamics segment asynchronously."""
    from llm_call import get_ai_response_async

    prompt = build_sd_verification_prompt(segment, signal=signal, idea=idea)

    # Collect source URLs from validation_data for grounding
    validation_data = segment.get('validation_data', {})
    all_urls = []
    for field_name in BASE_FIELDS:
        if field_name in validation_data:
            fd = validation_data[field_name]
            if isinstance(fd, dict):
                all_urls.extend(fd.get('source_urls', []))
    unique_urls = list(set(all_urls))

    try:
        response = await get_ai_response_async(
            prompt=prompt,
            output_format=_SDVerificationResponse,
            grounding=True,
            thinking_level="medium",
            url_context=unique_urls
        )

        if response is None:
            raise Exception("LLM returned None")

        return await parse_sd_verification_response(response, segment)

    except Exception as e:
        print(f"   ⚠️  Error verifying segment '{segment.get('segment_name')}': {e}")
        error_result = SDSegmentVerificationResult(
            segment_name=segment.get('segment_name', 'Unknown'),
            validation_tier=segment.get('validation_tier', 'peripheral'),
            field_results=[],
            overall_segment_quality='low',
            segment_confidence_avg=0.0,
            fields_verified=0,
            fields_corrected=0,
            fields_unable_to_verify=len(BASE_FIELDS),
            verification_timestamp=datetime.now().isoformat()
        )
        return error_result


# ==================== BATCH VERIFY ====================

def verify_all_sd_segments(
    segments: List[Dict[str, Any]],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
    batch_size: int = 3
) -> Dict[str, Any]:
    """
    Verify all 6 Struggle Dynamics segments in parallel batches.
    Sync wrapper around the async implementation.
    """
    return asyncio.run(verify_all_sd_segments_async(segments, signal, idea, batch_size))


async def verify_all_sd_segments_async(
    segments: List[Dict[str, Any]],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
    batch_size: int = 3
) -> Dict[str, Any]:
    """Async implementation: verifies segments in parallel batches."""
    verification_results: List[SDSegmentVerificationResult] = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]

        tasks = [verify_sd_segment_async(seg, signal=signal, idea=idea) for seg in batch]

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for j, result in enumerate(batch_results):
            seg_name = batch[j].get('segment_name', f'Segment {i+j+1}')

            if isinstance(result, Exception):
                print(f"   ❌ {seg_name}: Failed - {result}")
                verification_results.append(SDSegmentVerificationResult(
                    segment_name=seg_name,
                    validation_tier=batch[j].get('validation_tier', 'peripheral'),
                    field_results=[],
                    overall_segment_quality='low',
                    segment_confidence_avg=0.0,
                    fields_verified=0,
                    fields_corrected=0,
                    fields_unable_to_verify=len(BASE_FIELDS),
                    verification_timestamp=datetime.now().isoformat()
                ))
            elif result is not None:
                verification_results.append(result)

    summary = _generate_sd_summary(verification_results)
    corrected_segments = _apply_sd_corrections(segments, verification_results)

    return {
        'verification_results': verification_results,
        'summary': summary,
        'corrected_segments': corrected_segments,
    }


# ==================== SUMMARY ====================

def _generate_sd_summary(results: List[SDSegmentVerificationResult]) -> SDVerificationSummary:
    total_fields = sum(len(r.field_results) for r in results)
    high_struggle = len([r for r in results if r.validation_tier == 'high-struggle'])
    peripheral = len([r for r in results if r.validation_tier == 'peripheral'])
    avg_conf = sum(r.segment_confidence_avg for r in results) / len(results) if results else 0.0

    return SDVerificationSummary(
        total_segments_verified=len(results),
        total_fields_verified=total_fields,
        verified_accurate=sum(r.fields_verified for r in results),
        verified_corrected=sum(r.fields_corrected for r in results),
        unable_to_verify=sum(r.fields_unable_to_verify for r in results),
        average_confidence=avg_conf,
        high_struggle_segments=high_struggle,
        peripheral_segments=peripheral,
        high_quality_segments=len([r for r in results if r.overall_segment_quality == 'high']),
        medium_quality_segments=len([r for r in results if r.overall_segment_quality == 'medium']),
        low_quality_segments=len([r for r in results if r.overall_segment_quality == 'low']),
    )


# ==================== APPLY CORRECTIONS ====================

def _apply_sd_corrections(
    original_segments: List[Dict[str, Any]],
    verification_results: List[SDSegmentVerificationResult]
) -> List[Dict[str, Any]]:
    """
    Apply verification corrections back to the original segment dicts.
    Returns segments in the same schema (StruggleDynamicsSegment) with corrected data.
    """
    verification_map = {r.segment_name: r for r in verification_results}
    corrected = []

    for seg in original_segments:
        seg_name = seg.get('segment_name', '')
        corrected_seg = seg.copy()

        if seg_name in verification_map:
            vr = verification_map[seg_name]

            # Update validation_data fields
            if 'validation_data' in corrected_seg:
                vd = corrected_seg['validation_data']
                for field_result in vr.field_results:
                    if field_result.field_name in BASE_FIELDS and field_result.field_name in vd:
                        updated_value = (
                            field_result.corrected_value
                            if field_result.correction_needed and field_result.corrected_value
                            else field_result.verified_value
                        )
                        if isinstance(vd[field_result.field_name], dict):
                            vd[field_result.field_name]['value'] = updated_value
                            vd[field_result.field_name]['verified_sources'] = field_result.verification_sources
                            vd[field_result.field_name]['verification_status'] = field_result.verification_status
                            vd[field_result.field_name]['confidence_score'] = field_result.confidence_score
                        else:
                            vd[field_result.field_name] = {
                                'value': updated_value,
                                'source_urls': field_result.source_urls,
                                'verified_sources': field_result.verification_sources,
                                'verification_status': field_result.verification_status,
                                'confidence_score': field_result.confidence_score
                            }

            # Update acuteness_rationale
            if vr.acuteness_rationale_updated:
                corrected_seg['acuteness_rationale'] = vr.acuteness_rationale_updated
                corrected_seg['acuteness_rationale_original'] = vr.acuteness_rationale_original

            corrected_seg['_verification_metadata'] = {
                'verified': True,
                'verification_timestamp': vr.verification_timestamp,
                'overall_quality': vr.overall_segment_quality,
                'confidence_avg': vr.segment_confidence_avg,
                'fields_verified': vr.fields_verified,
                'fields_corrected': vr.fields_corrected,
                'fields_unable_to_verify': vr.fields_unable_to_verify
            }
        else:
            corrected_seg['_verification_metadata'] = {
                'verified': False,
                'reason': 'Not found in verification results'
            }

        corrected.append(corrected_seg)

    return corrected
