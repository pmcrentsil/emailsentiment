
import json, logging, os, uuid
import azure.functions as func
from common.clients import (load_settings, make_text_analytics_client, make_content_safety_client,
                            make_openai_client, make_blob_client, write_json, now_iso)
from common.models import TriageInput, SentimentResult, GPTClassification, TriageOutput
from common.logic import map_safety, combine_priority, routing_hint
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.function_name(name="triage")
@app.route(route="triage", methods=["POST"])
def triage(req: func.HttpRequest) -> func.HttpResponse:
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

    # 1) Content Safety
    cs_resp = cs.analyze_text(AnalyzeTextOptions(text=ti.body, categories=[TextCategory.HATE, TextCategory.VIOLENCE, TextCategory.SELF_HARM, TextCategory.SEXUAL]))
    safety = map_safety(cs_resp)

    # 2) Sentiment
    sa = ta.analyze_sentiment([ti.body])[0]
    sentiment = SentimentResult(sentiment=sa.sentiment, confidence={
        "positive": sa.confidence_scores.positive,
        "neutral": sa.confidence_scores.neutral,
        "negative": sa.confidence_scores.negative
    })

    # 3) GPT classification
    system = "You are an email triage assistant for IT support. Classify priority as high, medium, or low and explain briefly. Suggest 1-3 actions."
    user = f"Subject: {ti.subject}\nBody: {ti.body}\nSender: {ti.sender}\nImportance: {ti.importance}"
    chat = oa.chat.completions.create(
        model=s["openai_deployment"],
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.0,
        max_tokens=250
    )
    msg = chat.choices[0].message.content
    # naive parse to fields
    pr="medium"; reason=msg; actions=[]
    low = msg.lower()
    if "high" in low: pr="high"
    elif "low" in low: pr="low"
    if "actions:" in low:
        actions = [a.strip("- •").strip() for a in msg.split("Actions:")[-1].splitlines() if a.strip()][:3]
    gpt = GPTClassification(priority=pr, reason=reason, suggested_actions=actions)

    # Combine & route
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

    # Persist to blob
    name = f"{out.metadata['id']}.json"
    write_json(bs, s["blob_container"], name, json.loads(out.model_dump_json()))

    return func.HttpResponse(out.model_dump_json(), status_code=200, mimetype="application/json")
