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
    id: str = Field(description="Unique identifier for this segment (e.g., '1', '2', '3', ...)")
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
    ai_response: str = Field(..., description="The AI assistant's conversational response about struggle dynamics")


# ============================================================================
# STRUGGLE DYNAMICS VERIFICATION MODELS
# ============================================================================

class SDFieldVerification(BaseModel):
    """Single field verification result returned by the LLM for SD segments"""
    verified_value: str
    confidence_score: int
    discrepancies: List[str] = Field(default_factory=list)
    correction_needed: bool
    corrected_value: str = ""
    verification_sources: List[str] = Field(default_factory=list)


class SDVerificationResponse(BaseModel):
    """LLM output model for SD segment verification"""
    behavioral_evidence: SDFieldVerification
    pain_intensity: SDFieldVerification
    current_solutions: SDFieldVerification
    segment_accessibility: SDFieldVerification
    updated_acuteness_rationale: str
    ai_response: str = Field(default="", description="The AI assistant's conversational response about segment verification")


# ============================================================================
# MARKET SIZING GENERATION MODELS
# ============================================================================

class StruggleAwarePopulation(BaseModel):
    """Struggle-aware population data with sources"""
    total_population: int = Field(description="Total addressable population in location")
    population_source: str = Field(description="Source for population data (report name + year)")
    population_source_urls: List[str] = Field(default_factory=list, description="Direct URLs for the population source (e.g. census page, report URL)")
    prevalence_rate: float = Field(description="Decimal: what % actually experience this struggle", ge=0, le=1)
    prevalence_source: str = Field(description="Source for prevalence rate (report name + year)")
    prevalence_source_urls: List[str] = Field(default_factory=list, description="Direct URLs for the prevalence/struggle rate source")
    struggle_aware_count: int = Field(description="Calculated: those who actually feel the pain")
    calculation_logic: str = Field(description="Explanation of filtering logic")
    confidence: str = Field(description="High, Medium, or Low based on source quality")


class ComparableSolution(BaseModel):
    """A real competitor solution with pricing"""
    solution_name: str = Field(description="Name of comparable solution")
    price: str = Field(description="Annual/monthly price")
    source: str = Field(description="Citation for pricing (report name or URL)")
    source_url: str = Field(default="", description="Direct URL to the pricing page or source (e.g. https://competitor.com/pricing)")


class EnhancedPricingScenario(BaseModel):
    """Pricing scenario with real market data and sources"""
    tier: str = Field(description="Low / Volume, Mid / SaaS, or High / Premium")
    annual_price: int = Field(description="Annual price in USD")
    local_price: str = Field(description="Price in local currency if different (e.g., '₹4,000')")
    pricing_rationale: str = Field(description="4-6 sentences explaining price with market benchmark citations")
    pricing_source_urls: List[str] = Field(default_factory=list, description="URLs backing the pricing rationale (industry reports, surveys, market data)")
    comparable_solutions: List[ComparableSolution] = Field(description="2-3 real competitors with prices")
    sam_revenue: int = Field(description="struggle_aware_count × annual_price")
    capture_rate: str = Field(description="Realistic Year 1 capture rate (e.g., '2%')")
    som_year_1: int = Field(description="Calculated SOM for Year 1")
    som_reasoning: str = Field(description="Why this capture rate is realistic")


class EnhancedMarketSizing(BaseModel):
    """Complete market sizing with struggle-aware counts and source-backed pricing"""
    segment_name: str = Field(description="Name of the segment being analyzed")
    location: str = Field(description="Geographic location (e.g., 'India', 'US', 'UK')")
    struggle_aware_population: StruggleAwarePopulation = Field(description="Struggle-aware population data")
    pricing_scenarios: List[EnhancedPricingScenario] = Field(
        description="3 pricing scenarios with sources",
        min_length=3,
        max_length=3
    )
    recommended_scenario: str = Field(description="Low, Mid, or High")
    recommendation_reasoning: str = Field(description="Why this pricing tier fits best")
    data_sources: List[str] = Field(description="All sources used (URLs, report names, etc.)")
    api_grounding_sources: List[str] = Field(
        default_factory=list,
        description="URLs from Google Search grounding (extracted from API metadata)"
    )
    ai_response: str = Field(..., description="The AI assistant's conversational response about market sizing")


# ============================================================================
# MARKET SIZING VERIFICATION MODELS
# ============================================================================

class FieldVerificationData(BaseModel):
    """Single field verification result returned by the LLM"""
    field_name: str = Field(description="Name of the field being verified (e.g., 'total_population', 'prevalence_rate', 'pricing_tier_1')")
    pricing_tier: Optional[str] = Field(default=None, description="Pricing tier name if this is pricing data")
    verified_value: str = Field(description="The verified value found through research, or 'Unable to verify' if not found")
    confidence_score: int = Field(description="Confidence in verification from 0-100")
    discrepancies: List[str] = Field(default_factory=list, description="List of discrepancies found between claimed and verified values")
    correction_needed: bool = Field(description="Whether the claimed value needs correction")
    corrected_value: str = Field(default="", description="Corrected value if correction_needed is true")
    verification_sources: List[str] = Field(default_factory=list, description="URLs used to verify this field")
    verified_source_urls: List[str] = Field(default_factory=list, description="Direct URLs that confirm or correct the source URLs originally cited in the generation output")


class MarketVerificationLLMOutput(BaseModel):
    """LLM output model for market sizing verification"""
    fields: List[FieldVerificationData] = Field(description="Verification results for each field in the market sizing data")
    ai_response: str = Field(..., description="The AI assistant's conversational response about market sizing verification")


# ============================================================================
# PRE-COMPUTED OUTPUT SCHEMAS (model_json_schema)
# ============================================================================

# Segment generation
struggle_dynamics_output_format = StruggleDynamicsList.model_json_schema()

# Segment verification (LLM output)
sd_verification_output_format = SDVerificationResponse.model_json_schema()

# Market sizing generation
market_sizing_output_format = EnhancedMarketSizing.model_json_schema()

# Market sizing verification (LLM output)
market_verification_output_format = MarketVerificationLLMOutput.model_json_schema()
