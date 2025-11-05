from typing import Dict, Any, List
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from common.models import SafetyResult, SafetyCategory, SentimentResult, GPTClassification


def map_safety(resp) -> SafetyResult:
    """
    Map Azure Content Safety response into our SafetyResult.
    Any category with severity >= 4 triggers `blocked=True`.
    """
    blocked = False
    cats: List[SafetyCategory] = []
    if resp and getattr(resp, "categories_analysis", None):
        for ca in resp.categories_analysis:
            cats.append(SafetyCategory(category=str(ca.category), severity=ca.severity))
            if ca.severity is not None and ca.severity >= 4:
                blocked = True
    return SafetyResult(blocked=blocked, categories=cats)


def apply_security_overrides(gpt: GPTClassification, safety: SafetyResult) -> GPTClassification:
    """
    If Content Safety blocks the message, force GPT guidance to a security playbook.
    This prevents business-y suggestions on risky/blocked content.
    """
    if not safety.blocked:
        return gpt

    return GPTClassification(
        priority="blocked",
        reason=(
            "Content flagged by safety service (e.g., violence/gang coordination/contraband). "
            "Quarantine and escalate to security."
        ),
        suggested_actions=[
            "Quarantine the message (do not deliver to recipient).",
            "Open an incident and notify Intelligence Unit / Security.",
            "Preserve full headers and body for evidence.",
            "Add sender/account to watchlist pending review."
        ],
    )


def combine_priority(safety: SafetyResult, sentiment: SentimentResult, gpt: GPTClassification) -> str:
    """
    Priority rules:
      1) Safety block wins -> 'blocked'
      2) Otherwise, if sentiment is negative AND GPT reason implies urgency or GPT already says high -> 'high'
      3) Else use GPT's priority (normalized to lowercase)
    """
    if safety.blocked:
        return "blocked"

    if sentiment.sentiment.lower() == "negative" and (
        "urgent" in (gpt.reason or "").lower() or gpt.priority.lower() == "high"
    ):
        return "high"

    return gpt.priority.lower()


def routing_hint(priority: str) -> str:
    """
    Map final priority to a routing destination.
    """
    if priority == "blocked":
        return "Security Review / Intelligence Unit"
    if priority == "high":
        return "Teams + ITSM Ticket"
    if priority == "medium":
        return "Agent Queue"
    return "Auto-reply / Archive"
