from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ReasoningCard(BaseModel):
    type: str = Field(description="EVIDENCE or THREAT")
    claim: str = Field(description="Summary of finding")
    evidence: str = Field(description="What data supports this")
    uncertainty: str = Field(description="What could be wrong or missing")

class Recommendation(BaseModel):
    type: str = Field(description="VERIFY, MONITOR, or INTERVENE")
    title: str = Field(description="Action title")
    is_allowed: bool = Field(description="Must match input context allowed status")
    blocked_reasons: List[str] = Field(default_factory=list, description="Why it is blocked if not allowed")
    why_it_matters: str = Field(description="Benefit of doing this")
    how_to_do_it_steps: List[str] = Field(default_factory=list, description="Actionable steps")
    risk_if_wrong: str = Field(description="LOW, MED, or HIGH")

class LearningModule(BaseModel):
    level: str = Field(description="BEGINNER, INTERMEDIATE, or EXPERT")
    micro_lesson: str = Field(description="A 3-8 line educational snippet tailored to the user's level about the core concepts involved.")
    definitions: Dict[str, str] = Field(default_factory=dict)

class FollowUp(BaseModel):
    question: str = Field(description="Relevant question to clarify context. Exclude already known context.")
    why: str = Field(description="Why are you asking this?")

class InternalMemoryUpdate(BaseModel):
    experience_level_upgrade: Optional[str] = Field(description="If the user demonstrates higher knowledge, suggest an upgrade to INTERMEDIATE or EXPERT. Null otherwise.")
    new_known_facts: Dict[str, str] = Field(default_factory=dict, description="New persistent facts learned from user (e.g. soil texture, irrigation type)")
    closed_loops: List[str] = Field(default_factory=list, description="IDs or names of pending tasks the user just confirmed they did")

class ARFResponse(BaseModel):
    headline: str = Field(description="1 sentence title summarizing field status")
    direct_answer: str = Field(description="Direct answer to user's specific question")
    suitability_score: str = Field(description="Pure agronomic feasibility percentage e.g., '65%'")
    confidence_badge: str = Field(description="HIGH, MED, or LOW")
    confidence_reason: str = Field(description="Why the confidence badge is what it is")
    what_it_means: str = Field(description="Agronomic interpretation of the situation")
    reasoning_cards: List[ReasoningCard] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    learning: LearningModule
    followups: List[FollowUp] = Field(default_factory=list)
    internal_memory_updates: Optional[InternalMemoryUpdate] = None
