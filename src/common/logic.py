from typing import Dict, Any, List
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from common.models import SafetyResult, SafetyCategory, SentimentResult, GPTClassification

def map_safety(resp) -> SafetyResult:
    blocked = False
    cats: List[SafetyCategory] = []
    if resp and resp.categories_analysis:
        for ca in resp.categories_analysis:
            cats.append(SafetyCategory(category=str(ca.category), severity=ca.severity))
            if ca.severity and ca.severity >= 4:
                blocked = True
    return SafetyResult(blocked=blocked, categories=cats)

def combine_priority(safety: SafetyResult, sentiment: SentimentResult, gpt: GPTClassification) -> str:
    # Rules: block wins; else if negative & reason contains 'urgent' -> High; else GPT
    if safety.blocked:
        return "blocked"
    if sentiment.sentiment.lower() == "negative" and ("urgent" in gpt.reason.lower() or gpt.priority.lower()=="high"):
        return "high"
    return gpt.priority.lower()

def routing_hint(priority: str) -> str:
    if priority == "blocked":
        return "Auto-reply / Archive"
    if priority == "high":
        return "Teams + ITSM Ticket"
    if priority == "medium":
        return "Agent Queue"
    return "Auto-reply / Archive"
