import json, logging, uuid
import azure.functions as func
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from common.clients import (
    load_settings, make_text_analytics_client, make_content_safety_client,
    make_openai_client, make_blob_client, write_json, now_iso
)
from common.models import TriageInput, SentimentResult, GPTClassification, TriageOutput
from common.logic import map_safety, combine_priority, routing_hint


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing email triage request...")

    try:
        payload = req.get_json()
    except Exception:
        return func.HttpResponse(json.dumps({"error": "Invalid JSON"}), status_code=400)

    ti = TriageInput(**payload)
    s = load_settings()
    ta = make_text_analytics_client(s)
    cs = make_content_safety_client(s)
    oa = make_openai_client(s)
    bs = make_blob_client(s)

    # 1️⃣ Content Safety
    cs_resp = cs.analyze_text(AnalyzeTextOptions(
        text=ti.body,
        categories=[TextCategory.HATE, TextCategory.VIOLENCE, TextCategory.SELF_HARM, TextCategory.SEXUAL]
    ))
    safety = map_safety(cs_resp)

    # 2️⃣ Sentiment
    sa = ta.analyze_sentiment([ti.body])[0]
    sentiment = SentimentResult(
        sentiment=sa.sentiment,
        confidence={
            "positive": sa.confidence_scores.positive,
            "neutral": sa.confidence_scores.neutral,
            "negative": sa.confidence_scores.negative
        }
    )

    # 3️⃣ GPT classification
    system = "You are an IT support triage assistant. Classify email priority (high/medium/low) and suggest 1-3 actions."
    user = f"Subject: {ti.subject}\nBody: {ti.body}\nSender: {ti.sender}\nImportance: {ti.importance}"
    chat = oa.chat.completions.create(
        model=s["openai_deployment"],
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=250
    )

    msg = chat.choices[0].message.content or ""
    pr = "medium"
    if "high" in msg.lower(): pr = "high"
    elif "low" in msg.lower(): pr = "low"

    gpt = GPTClassification(priority=pr, reason=msg, suggested_actions=msg.split("\n"))

    # Combine and route
    combined = combine_priority(safety, sentiment, gpt)
    route = routing_hint(combined)

    out = TriageOutput(
        safety=safety,
        sentiment=sentiment,
        gpt=gpt,
        combined_priority=combined,
        routing_hint=route,
        metadata={
            "id": str(uuid.uuid4()),
            "timestamp": now_iso(),
            "subject": ti.subject,
            "sender": ti.sender
        }
    )

    write_json(bs, s["blob_container"], f"{out.metadata['id']}.json", json.loads(out.model_dump_json()))
    return func.HttpResponse(out.model_dump_json(), mimetype="application/json", status_code=200)
