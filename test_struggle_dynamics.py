"""
Test the full Struggle Dynamics pipeline (all 4 steps):
  1. SD Segment Generation (6 segments)
  2. SD Segment Verification (3 high-struggle)
  3. Market Sizing Generation (3 segments, 3 pricing tiers each)
  4. Market Sizing Verification

All imports are from the struggle_dynamics/ module — no root-level dependencies.

Usage:
  python test_struggle_dynamics.py --test 1
  python test_struggle_dynamics.py --test 2
  python test_struggle_dynamics.py -t 1
"""
import sys
import os
import json
import argparse
import asyncio
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controller import (
    generate_struggle_dynamics_segments,
    generate_market_sizings,
    market_sizings_to_dicts,
)
from output_formats import StruggleDynamicsList, StruggleDynamicsSegment
from struggle_dynamics_verification import verify_all_sd_segments
from market_sizing_verification import verify_all_market_sizings
from helpers import save_to_json

# ============================================================================
# TEST DATA  (mirroring real pipeline log outputs)
# ============================================================================

# Test 1: Micro-gym booking app — Chicago Suburban Parents
# Source: prompts_log_user_8410d36d-b94f-4a3d-8a12-e49f0f9f00d6.json
TEST_1 = {
    "name": "micro_gym_suburban_parents",
    "confirmed_user": "Suburban Parents",
    "confirmed_struggle": (
        "Scheduling friction and lack of easy access to local fitness spaces "
        "for short, efficient workouts"
    ),
    "confirmed_solution": (
        "A mobile app for automated 30-minute window finding, micro-gym booking, "
        "and smart lock integration"
    ),
    "selected_signal": {
        "id": "1",
        "signal_name": "The Velocity Protocol",
        "signal_vector": "Frictionless Access",
        "target_user": "Time-starved Chicago parents managing tight logistical loops between drop-offs",
        "mini_signal": "Turn dead scheduling gaps into fitness intervals instantly",
        "strategic_frame": {
            "customer_mission": (
                "When managing chaotic family schedules, Suburban Parents need on-demand, "
                "proximity-based booking to recapture lost time for health."
            ),
            "customer_story": {
                "the_moment": "When I have a 45-minute gap between soccer drop-off and the grocery run...",
                "the_solution": "Help me instantly find and access a gym pod within a 5-minute drive...",
                "the_win": "So that I can maintain my health without disrupting the family logistics."
            },
            "business_logic": {
                "company_type": "Hyper-Local Marketplace",
                "key_metric": "Repeat Booking Frequency",
                "model": "Transaction Fee / Pay-As-You-Go",
                "strategic_bet": "Prioritizing network density and proximity over equipment variety or luxury."
            },
            "founders_path": {
                "builder_dna": "Logistics Aggregator",
                "the_hard_part": "Solving the liquidity cold-start problem in low-density suburbs.",
                "user_vibe": "Utilitarian Efficiency"
            }
        },
        "identity_core": {
            "identity_shift": "From 'Harried Chauffeur' \u2192 To 'Time Arbitrageur'",
            "psychological_compilation": {
                "the_logic": "They don't pay for fitness; they pay to eliminate the guilt of wasted time.",
                "incoherence_check": "A complex 5-step check-in process or waiting for keys.",
                "implied_feature": "One-tap 'Book Nearest Now' button with instant smart-lock code generation."
            },
            "future_history": (
                "I used to sit in my car doom-scrolling while waiting for my kid's practice to end. "
                "Now, I hit one button and I'm lifting weights three blocks away. I reclaimed my day."
            )
        }
    },
    "user_profile_title": "startup_founder",
    "target_location": "Chicago suburbs, US",
    "language_level": "STANDARD_BUSINESS",
}

# Test 2: Hobbyist micro-insurance — Whole US
# Source: prompts_log_user_fdcb6b16-12a9-4e54-b95a-b38d33d00c5e.json
TEST_2 = {
    "name": "hobbyist_micro_insurance",
    "confirmed_user": "Hobbyists",
    "confirmed_struggle": (
        "Hobbyists cannot demo projects at pop-ups because venues demand expensive liability coverage."
    ),
    "confirmed_solution": (
        "Per-hour parametric micro-policies triggered by attendance and activity type."
    ),
    "selected_signal": {
        "id": "3",
        "signal_name": "Guardian",
        "signal_vector": "Parametric Precision",
        "target_user": "The 'High-Stakes Maker' (drones, robotics, kinetics) with expensive gear and genuine accident risk.",
        "mini_signal": "Surgical coverage for complex, high-risk demos.",
        "strategic_frame": {
            "customer_mission": (
                "When demoing dangerous or expensive hardware, the maker needs specific risk parameters "
                "to prevent financial ruin."
            ),
            "customer_story": {
                "the_moment": "When I am operating heavy kinetics or drones near a crowd...",
                "the_solution": "Help me to isolate the exact liability triggers for my specific machinery...",
                "the_win": "So that I can perform without the fear of a lawsuit bankrupting me."
            },
            "business_logic": {
                "company_type": "MGA (Managing General Agent)",
                "key_metric": "Loss Ratio (Underwriting Accuracy)",
                "model": "Variable Premium (Risk-Adjusted)",
                "strategic_bet": "Deep actuarial data on niche risks that large insurers ignore."
            },
            "founders_path": {
                "builder_dna": "Systems Engineer",
                "the_hard_part": "Underwriting: Getting the data to price these niche risks profitably.",
                "user_vibe": "Trusted Shield"
            }
        },
        "identity_core": {
            "identity_shift": "From 'Exposed & Anxious' \u2192 To 'Secure & Calculated'",
            "psychological_compilation": {
                "the_logic": "They know their activity is dangerous; they pay for the peace of mind that their assets are safe.",
                "incoherence_check": "Generic 'blanket' policies that exclude specific machinery usage.",
                "implied_feature": "Activity-specific toggle switches (e.g., 'Drone Mode', 'Pyro Mode')."
            },
            "future_history": (
                "I used to be terrified that one malfunction would cost me my house. "
                "Now I toggle my coverage to match my exact setup, and I focus entirely on the show."
            )
        }
    },
    "user_profile_title": "startup_founder",
    "target_location": "whole US",
    "language_level": "STANDARD_BUSINESS",
}

TESTS = {"1": TEST_1, "2": TEST_2}


# ============================================================================
# CLI
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Struggle Dynamics segment generation + verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Tests:
  1 - Micro-gym booking app (Chicago Suburban Parents)
  2 - Hobbyist micro-insurance (Whole US)

Examples:
  python test_struggle_dynamics.py --test 1
  python test_struggle_dynamics.py -t 2
        """,
    )
    parser.add_argument(
        "--test", "-t",
        type=str,
        choices=["1", "2"],
        required=True,
        help="Test number to run (1 or 2)",
    )
    return parser.parse_args()


# ============================================================================
# MAIN
# ============================================================================

args = parse_args()
td = TESTS[args.test]
TEST_NAME = td["name"]

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
test_dir = Path(f"test_results_sd_low/{TEST_NAME}_{timestamp}")
test_dir.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("STRUGGLE DYNAMICS — SEGMENT GENERATION + VERIFICATION")
print("=" * 80)
print(f"\nTest:      {TEST_NAME}")
print(f"User:      {td['confirmed_user']}")
print(f"Location:  {td['target_location']}")
print(f"Signal:    {td['selected_signal']['signal_name']}")
print(f"Results:   {test_dir}")

# ============================================================================
# STEP 1: GENERATE 6 SEGMENTS
# ============================================================================
print(f"\n{'='*80}")
print("STEP 1: GENERATING 6 STRUGGLE DYNAMICS SEGMENTS")
print("=" * 80)

sd_result = generate_struggle_dynamics_segments(
    confirmed_user=td["confirmed_user"],
    confirmed_struggle=td["confirmed_struggle"],
    confirmed_solution=td["confirmed_solution"],
    selected_signal=td["selected_signal"],
    user_profile_title=td["user_profile_title"],
    target_location=td["target_location"],
    language_level=td["language_level"],
)

if not sd_result:
    print("\n❌ FAILED to generate segments")
    sys.exit(1)

all_segments = sd_result.struggle_dynamics_segments
high_struggle = [s for s in all_segments if s.validation_tier == "high-struggle"]
peripheral = [s for s in all_segments if s.validation_tier == "peripheral"]

print(f"\n✅ Generated {len(all_segments)} segments")

print(f"\n🔥 HIGH-STRUGGLE SEGMENTS ({len(high_struggle)}):")
for i, seg in enumerate(high_struggle, 1):
    dq = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(
        seg.validation_data.data_quality, "⚪"
    )
    print(f"   {i}. {seg.segment_name} {dq} [{seg.validation_data.data_quality}]")
    print(f"      {seg.acuteness_rationale[:100]}...")
    print(f"      Intensity: {seg.struggle_intensity} | Frequency: {seg.struggle_frequency}")
    if seg.advanced_trend_analysis:
        print(f"      Trend Verdict: {seg.advanced_trend_analysis.trend_verdict}")

print(f"\n⚪ PERIPHERAL SEGMENTS ({len(peripheral)}):")
for i, seg in enumerate(peripheral, 1):
    dq = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(
        seg.validation_data.data_quality, "⚪"
    )
    print(f"   {i}. {seg.segment_name} {dq} [{seg.validation_data.data_quality}]")
    print(f"      {seg.acuteness_rationale[:100]}...")

# Save raw generation output
gen_output = {
    "test_info": {"test_name": TEST_NAME, "timestamp": timestamp, "test_directory": str(test_dir)},
    "input": {
        "confirmed_user": td["confirmed_user"],
        "confirmed_struggle": td["confirmed_struggle"],
        "confirmed_solution": td["confirmed_solution"],
        "selected_signal": td["selected_signal"],
        "user_profile_title": td["user_profile_title"],
        "target_location": td["target_location"],
        "language_level": td["language_level"],
    },
    "segments": [s.model_dump() for s in all_segments],
    "total_segments": sd_result.total_segments,
    "generation_notes": sd_result.generation_notes,
}
segments_file = test_dir / "segments.json"
save_to_json(gen_output, segments_file)
print(f"\n💾 Segments saved to: {segments_file}")

# ============================================================================
# STEP 2: VERIFY ALL 6 SEGMENTS
# ============================================================================
print(f"\n{'='*80}")
print("STEP 2: VERIFYING 3 HIGH-STRUGGLE SEGMENTS")
print("=" * 80)

idea_context = {
    "confirmed_user": td["confirmed_user"],
    "confirmed_struggle": td["confirmed_struggle"],
    "confirmed_solution": td["confirmed_solution"],
    "target_location": td["target_location"],
}

# Only verify the first 3 (high-struggle); peripheral segments skip verification
high_struggle_segs = [s.model_dump() for s in all_segments[:3]]
peripheral_segs = [s.model_dump() for s in all_segments[3:]]

verification_result = verify_all_sd_segments(
    segments=high_struggle_segs,
    signal=td["selected_signal"],
    idea=idea_context,
    batch_size=3,
)

ver_summary = verification_result["summary"]
print(f"\n📊 Verification Summary:")
print(f"   Total Segments Verified: {ver_summary.total_segments_verified}")
print(f"   Total Fields Verified:   {ver_summary.total_fields_verified}")
print(f"   ✓  Verified Accurate:    {ver_summary.verified_accurate}")
print(f"   ✏️   Verified Corrected:  {ver_summary.verified_corrected}")
print(f"   ❌ Unable to Verify:     {ver_summary.unable_to_verify}")
print(f"   Average Confidence:      {ver_summary.average_confidence:.1f}%")
print(f"\n   Segment Breakdown:")
print(f"   🔥 High-Struggle verified: {ver_summary.high_struggle_segments}")
print(f"   ⚪ Peripheral skipped:     {len(peripheral_segs)} (no verification)")
print(f"\n   Data Quality After Verification:")
print(f"   🟢 High:   {ver_summary.high_quality_segments}")
print(f"   🟡 Medium: {ver_summary.medium_quality_segments}")
print(f"   🔴 Low:    {ver_summary.low_quality_segments}")

# Save verification results
ver_output = {
    "test_info": {"test_name": TEST_NAME, "timestamp": timestamp, "test_directory": str(test_dir)},
    "verification_summary": ver_summary.model_dump(),
    "verification_results": [r.model_dump() for r in verification_result["verification_results"]],
}
ver_file = test_dir / "verification_results.json"
save_to_json(ver_output, ver_file)
print(f"\n💾 Verification results saved to: {ver_file}")

# Save corrected segments: verified high-struggle (3) + unverified peripheral (3)
all_corrected = verification_result["corrected_segments"] + peripheral_segs
corrected_output = {
    "test_info": {
        "test_name": TEST_NAME,
        "timestamp": timestamp,
        "test_directory": str(test_dir),
        "note": "High-struggle segments are verified/corrected. Peripheral segments are passed through as-is.",
    },
    "segments": all_corrected,
    "total_segments": len(all_corrected),
    "metadata": {
        "verified_segments": len(verification_result["corrected_segments"]),
        "unverified_peripheral_segments": len(peripheral_segs),
    },
}
corrected_file = test_dir / "segments_corrected.json"
save_to_json(corrected_output, corrected_file)
print(f"💾 Corrected segments saved to: {corrected_file}")
print(f"   → Use this file for production (same schema, verified data)")

# ============================================================================
# STEP 3: MARKET SIZING GENERATION (top 3 high-struggle segments)
# ============================================================================
print(f"\n{'='*80}")
print("STEP 3: MARKET SIZING — 3 SEGMENTS × 3 PRICING TIERS")
print("=" * 80)

idea_for_market = {
    "problem":     td["confirmed_struggle"],
    "solution":    td["confirmed_solution"],
    "target_user": td["confirmed_user"],
}

corrected_high_struggle = verification_result["corrected_segments"]  # already top 3

ms_results = generate_market_sizings(
    segments=corrected_high_struggle,
    jtbd=td["selected_signal"],
    idea=idea_for_market,
    location=td["target_location"],
    max_segments=3,
)

market_sizing_dicts = market_sizings_to_dicts(ms_results)

print(f"\n✅ Market sizing complete:")
for ms in market_sizing_dicts:
    if not ms:
        continue
    seg_name = ms.get("segment_name", "Unknown")
    pop      = ms.get("struggle_aware_population", {})
    count    = pop.get("struggle_aware_count", 0)
    conf     = pop.get("confidence", "?")
    rec      = ms.get("recommended_scenario", "?")
    tiers    = ms.get("pricing_scenarios", [])
    prices   = [f"{t.get('tier','?')} ${t.get('annual_price',0):,}" for t in tiers]
    print(f"   📊 {seg_name}")
    print(f"      Struggle-Aware Count: {count:,} ({conf} confidence)")
    print(f"      Pricing Tiers:        {' | '.join(prices)}")
    print(f"      Recommended:          {rec}")

ms_raw_file = test_dir / "market_sizing_raw.json"
save_to_json(
    {
        "test_info": {"test_name": TEST_NAME, "timestamp": timestamp, "test_directory": str(test_dir)},
        "market_sizings": [ms for ms in market_sizing_dicts if ms],
        "total_segments": len([ms for ms in market_sizing_dicts if ms]),
    },
    ms_raw_file,
)
print(f"\n💾 Market sizing raw saved to: {ms_raw_file}")

# ============================================================================
# STEP 4: MARKET SIZING VERIFICATION
# ============================================================================
print(f"\n{'='*80}")
print("STEP 4: MARKET SIZING VERIFICATION")
print("=" * 80)

valid_sizings = [ms for ms in market_sizing_dicts if ms]

mv_result = verify_all_market_sizings(
    market_sizings=valid_sizings,
    jtbd=td["selected_signal"],
    idea=idea_for_market,
    batch_size=3,
)

mv_summary = mv_result["summary"]
print(f"\n📊 Market Verification Summary:")
print(f"   Segments Verified:   {mv_summary.total_segments_verified}")
print(f"   Total Fields:        {mv_summary.total_fields_verified}")
print(f"   ✓  Accurate:         {mv_summary.verified_accurate}")
print(f"   ✏️   Corrected:       {mv_summary.verified_corrected}")
print(f"   ❌ Unable to Verify: {mv_summary.unable_to_verify}")
print(f"   Avg Confidence:      {mv_summary.average_confidence:.1f}%")
print(f"   🟢 High:  {mv_summary.high_quality_segments}  "
      f"🟡 Medium: {mv_summary.medium_quality_segments}  "
      f"🔴 Low: {mv_summary.low_quality_segments}")

mv_verified_file = test_dir / "market_sizing_verified.json"
save_to_json(
    {
        "test_info": {"test_name": TEST_NAME, "timestamp": timestamp, "test_directory": str(test_dir)},
        "verification_summary": mv_summary.model_dump(),
        "corrected_market_sizings": mv_result["corrected_market_sizings"],
        "verification_results": [
            r.model_dump() for r in mv_result["verification_results"]
        ],
    },
    mv_verified_file,
)
print(f"\n💾 Market sizing verified saved to: {mv_verified_file}")

print(f"\n✅ All results saved to: {test_dir}/")
print(f"   • segments.json              — Raw generated segments (6 total)")
print(f"   • segments_corrected.json    — Verified SD segments (use for market sizing)")
print(f"   • market_sizing_raw.json     — Raw market sizing (3 segments × 3 tiers)")
print(f"   • market_sizing_verified.json — Corrected market sizing (use for production)")
