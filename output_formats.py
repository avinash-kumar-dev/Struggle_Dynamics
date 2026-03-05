"""
Pydantic schemas for the Struggle Dynamics module.
Contains only the models required for the 6-segment Struggle Dynamics pipeline.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class MarketDataField(BaseModel):
    """Individual market data point with its source URLs"""
    value: str = Field(description="The actual data point or finding")
    source_urls: List[str] = Field(description="URLs that support this specific claim")


class SegmentValidationData(BaseModel):
    """Segment validation data with granular source tracking for verification"""
    behavioral_evidence: MarketDataField = Field(description="Proof the segment exhibits the described behaviors with specific URLs (e.g., value: 'Study shows 73% check email during meetings', source_urls: ['https://research.com/...'])")
    pain_intensity: MarketDataField = Field(description="Evidence of how severe/urgent their pain is with specific URLs (e.g., value: 'Rated 8/10 urgency, willing to pay premium', source_urls: ['https://survey.com/...'])")
    current_solutions: MarketDataField = Field(description="What they use today and why it fails with specific URLs (e.g., value: '89% use spreadsheets but cite errors and time waste', source_urls: ['https://report.com/...'])")
    segment_accessibility: MarketDataField = Field(description="How easy to reach/acquire this segment with specific URLs (e.g., value: 'Active on LinkedIn, 3.2M members in groups', source_urls: ['https://linkedin.com/...'])")
    data_quality: str = Field(description="'high' (multiple credible sources per field), 'medium' (some sources), or 'low' (limited data available)")


class TemporalBecoming(BaseModel):
    """Two/Five year demand horizon"""
    two_year_horizon: str = Field(description="What they pay for today (e.g., Friction Reduction)")
    five_year_horizon: str = Field(description="What they will demand tomorrow (e.g., Agentic Autonomy)")


class AdvancedTrendAnalysis(BaseModel):
    """Trend analysis for high-struggle segments only"""
    tailwind: str = Field(description="Global force making this segment's struggle worse right now")
    headwind: str = Field(description="Biggest threat or market force that could kill this opportunity")
    smart_money_signal: str = Field(description="VC/competitor investment signals for this segment type")
    trend_verdict: str = Field(description="Accelerating, Stable, or Declining")
    future_trends: str = Field(description="Exponential events, macro-shifts, or tech disruptions ahead")
    temporal_becoming: TemporalBecoming = Field(description="Two and five year demand horizons")
    complementary_viral_loop: str = Field(description="The counterpart user and how they create a network effect")


class StruggleDynamicsSegment(BaseModel):
    """A single segment from the Struggle Dynamics phase (new 6-segment schema)"""
    validation_tier: str = Field(description="'high-struggle' (top 3) or 'peripheral' (bottom 3)")
    acuteness_rationale: str = Field(description="Why this segment was ranked high-struggle or peripheral based purely on pain intensity and hard data")
    segment_name: str = Field(description="Short, memorable name (3-5 words)")
    description: str = Field(description="Who they are and their context")
    context_circumstance: str = Field(description="When/where the struggle happens")
    key_constraints: List[str] = Field(description="Primary constraints: time, money, compliance, coordination, etc.")
    buyer_type: str = Field(description="self-serve, manager-approved, or procurement-driven")
    struggle_frequency: str = Field(description="daily, weekly, monthly, or occasional")
    struggle_intensity: str = Field(description="critical, high, medium, or low")
    existing_alternatives: List[str] = Field(description="What they use today")
    product_vibe: str = Field(description="Emotional/functional product personality for this segment")
    validation_data: SegmentValidationData = Field(description="Market evidence with sources (same schema as UserSegment)")
    advanced_trend_analysis: AdvancedTrendAnalysis = Field(
        description="Fully populated for high-struggle segments. For peripheral segments, set all string fields to 'N/A - peripheral segment'."
    )


class StruggleDynamicsList(BaseModel):
    """Output wrapper for 6-segment Struggle Dynamics generation"""
    struggle_dynamics_segments: List[StruggleDynamicsSegment] = Field(
        description="Exactly 6 segments: first 3 are high-struggle (ranked by pain intensity), last 3 are peripheral"
    )
    total_segments: int = Field(default=6, description="Always 6")
    generation_notes: str = Field(default="", description="Notes on segmentation approach")


# ============================================================================
# STRUGGLE DYNAMICS VERIFICATION MODELS
# ============================================================================

class FieldVerificationResult(BaseModel):
    """Verification result for a single field within a segment"""
    field_name: str
    claimed_value: str
    source_urls: List[str]
    verified_value: str
    confidence_score: int  # 0-100
    verification_status: str  # 'verified', 'corrected', 'unable_to_verify'
    discrepancies: List[str] = Field(default_factory=list)
    correction_needed: bool
    corrected_value: str = ""
    verification_sources_claimed: List[str] = Field(default_factory=list)
    verification_sources: List[str] = Field(default_factory=list)


class SDSegmentVerificationResult(BaseModel):
    """Verification result for one Struggle Dynamics segment (all fields)"""
    segment_name: str
    validation_tier: str  # 'high-struggle' or 'peripheral'
    field_results: List[FieldVerificationResult]
    overall_segment_quality: str  # 'high', 'medium', 'low'
    segment_confidence_avg: float
    fields_verified: int
    fields_corrected: int
    fields_unable_to_verify: int
    acuteness_rationale_original: str = ""
    acuteness_rationale_updated: str = ""
    search_queries_used: List[str] = Field(default_factory=list)
    grounding_chunks_used: List[Dict[str, Any]] = Field(default_factory=list)
    token_metrics: Dict[str, int] = Field(default_factory=dict)
    verification_timestamp: str


class SDVerificationSummary(BaseModel):
    """Aggregate statistics across all Struggle Dynamics segment verifications"""
    total_segments_verified: int
    total_fields_verified: int
    verified_accurate: int
    verified_corrected: int
    unable_to_verify: int
    average_confidence: float
    high_struggle_segments: int
    peripheral_segments: int
    high_quality_segments: int
    medium_quality_segments: int
    low_quality_segments: int
