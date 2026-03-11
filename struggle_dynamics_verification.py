"""
Struggle Dynamics Verification Pipeline
Verifies the 6-segment output from the Struggle Dynamics phase.

Public API
----------
verify_all_sd_segments(segments, signal, idea) -> dict
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from output_formats import SDVerificationResponse
from helpers import validate_urls_async
from dynamic_prompt_creator import build_sd_verification_prompt, SD_BASE_FIELDS


# ==================== ASYNC VERIFY ONE SEGMENT ====================

async def verify_sd_segment_async(
    segment: Dict[str, Any],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Optional[SDVerificationResponse]:
    """
    Verify one Struggle Dynamics segment asynchronously.

    Returns the LLM verification response with URL-validated sources,
    or None on error.
    """
    from llm_call import get_ai_response, LLM_MODEL
    from output_formats import sd_verification_output_format

    prompt = build_sd_verification_prompt(segment, signal=signal, idea=idea)

    # Collect source URLs from validation_data for grounding
    validation_data = segment.get('validation_data', {})
    all_urls = []
    for field_name in SD_BASE_FIELDS:
        if field_name in validation_data:
            fd = validation_data[field_name]
            if isinstance(fd, dict):
                all_urls.extend(fd.get('source_urls', []))
    unique_urls = list(set(all_urls))

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: get_ai_response(
                prompt=prompt,
                llm_model=LLM_MODEL,
                output_format=sd_verification_output_format,
                dynamic_thinking_level="medium",
                grounding=True,
                url_context=unique_urls,
            )
        )

        parsed = json.loads(raw)
        response = SDVerificationResponse.model_validate(parsed)

        # Validate verification_sources URLs in-place
        for field_name in SD_BASE_FIELDS:
            fv = getattr(response, field_name)
            if fv.verification_sources:
                fv.verification_sources = await validate_urls_async(fv.verification_sources)

        return response

    except Exception as e:
        print(f"   ⚠️  Error verifying segment '{segment.get('segment_name')}': {e}")
        return None


# ==================== BATCH VERIFY ====================

def verify_all_sd_segments(
    segments: List[Dict[str, Any]],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Verify all Struggle Dynamics segments in parallel batches.
    Sync wrapper around the async implementation.
    """
    return asyncio.run(verify_all_sd_segments_async(segments, signal, idea))


async def verify_all_sd_segments_async(
    segments: List[Dict[str, Any]],
    signal: Dict[str, Any] = None,
    idea: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Async implementation: verifies segments in parallel batches.

    Returns:
        Dict with:
          - verification_responses: {segment_name: SDVerificationResponse} for successful verifications
          - corrected_segments: list of corrected segment dicts
    """
    responses: Dict[str, SDVerificationResponse] = {}

    BATCH_SIZE = 3
    for i in range(0, len(segments), BATCH_SIZE):
        batch = segments[i:i + BATCH_SIZE]
        tasks = [verify_sd_segment_async(seg, signal=signal, idea=idea) for seg in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for j, result in enumerate(batch_results):
            seg_name = batch[j].get('segment_name', f'Segment {i+j+1}')
            if isinstance(result, Exception):
                print(f"   ❌ {seg_name}: Failed - {result}")
            elif result is not None:
                responses[seg_name] = result

    corrected_segments = _apply_sd_corrections(segments, responses)

    return {
        'verification_responses': responses,
        'corrected_segments': corrected_segments,
    }


# ==================== APPLY CORRECTIONS ====================

def _apply_sd_corrections(
    original_segments: List[Dict[str, Any]],
    responses: Dict[str, SDVerificationResponse],
) -> List[Dict[str, Any]]:
    """
    Apply verification corrections back to the original segment dicts.
    Works directly with LLM response objects — no intermediate result model needed.
    """
    corrected = []

    for seg in original_segments:
        seg_name = seg.get('segment_name', '')
        corrected_seg = seg.copy()

        if seg_name in responses:
            response = responses[seg_name]

            # Update validation_data field values
            if 'validation_data' in corrected_seg:
                vd = corrected_seg['validation_data']
                for field_name in SD_BASE_FIELDS:
                    if field_name not in vd:
                        continue
                    fv = getattr(response, field_name)
                    updated_value = (
                        fv.corrected_value
                        if fv.correction_needed and fv.corrected_value
                        else fv.verified_value
                    )
                    if isinstance(vd[field_name], dict):
                        vd[field_name]['value'] = updated_value
                        if fv.verification_sources:
                            vd[field_name]['source_urls'] = fv.verification_sources
                    else:
                        vd[field_name] = {
                            'value': updated_value,
                            'source_urls': fv.verification_sources,
                        }

            # Update acuteness_rationale
            if response.updated_acuteness_rationale:
                corrected_seg['acuteness_rationale'] = response.updated_acuteness_rationale

        corrected.append(corrected_seg)

    return corrected
