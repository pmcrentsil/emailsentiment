from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class SafetyCategory(BaseModel):
    category: str
    severity: int

class SafetyResult(BaseModel):
    blocked: bool = False
    categories: List[SafetyCategory] = []

class SentimentResult(BaseModel):
    sentiment: str
    confidence: Dict[str, float]

class GPTClassification(BaseModel):
    priority: str
    reason: str
    suggested_actions: List[str] = []

class TriageInput(BaseModel):
    subject: str = ""
    body: str = ""
    sender: Optional[str] = None
    to: Optional[List[str]] = None
    headers: Dict[str, Any] = {}
    importance: Optional[str] = None

class TriageOutput(BaseModel):
    safety: SafetyResult
    sentiment: SentimentResult
    gpt: GPTClassification
    combined_priority: str
    routing_hint: str
    metadata: Dict[str, Any] = {}
