import json
import requests
import streamlit as st
from datetime import datetime

# -----------------------------
# App Config & Styling
# -----------------------------
st.set_page_config(
    page_title="TDCJ - AI Email Sentiment Analysis",
    page_icon="📧",
    layout="wide",
)

CUSTOM_CSS = """
<style>
/* Layout tweaks */
.block-container {padding-top: 2rem !important;}

/* Card */
.card {border-radius: 16px; padding: 18px 18px; border: 1px solid #e5e7eb; box-shadow: 0 2px 20px rgba(0,0,0,0.04); background: #fff;}
.card h3 {margin-top: 0; margin-bottom: 0.5rem}

/* Badge styles */
.badges {display: flex; gap: 8px; flex-wrap: wrap;}
.badge {border-radius: 999px; padding: 6px 10px; font-size: 0.85rem; font-weight: 600; border: 1px solid rgba(0,0,0,0.06)}
.badge.gray {background: #f3f4f6}
.badge.green {background: #ecfdf5; color: #065f46; border-color: #a7f3d0}
.badge.yellow {background: #fffbeb; color: #92400e; border-color: #fde68a}
.badge.orange {background: #fff7ed; color: #9a3412; border-color: #fdba74}
.badge.red {background: #fef2f2; color: #991b1b; border-color: #fecaca}
.badge.blue {background: #eff6ff; color: #1e40af; border-color: #bfdbfe}

/* Priority chip */
.priority {display:inline-block; border-radius: 12px; padding: 6px 10px; font-weight:700}
.priority.blocked {background:#fee2e2; color:#991b1b}
.priority.high {background:#ffedd5; color:#9a3412}
.priority.medium {background:#e0f2fe; color:#1e40af}
.priority.low {background:#ecfdf5; color:#065f46}

/* Divider */
.hr {height:1px; background: #e5e7eb; margin: 14px 0}

.small {opacity: 0.8; font-size: 0.9rem}
.mono {font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------
# Header
# -----------------------------
left, right = st.columns([0.8, 0.2])
with left:
    st.markdown("# TDCJ – AI Email Sentiment Analysis")
    st.markdown(
        "Analyze inmate email content for **safety**, **sentiment**, and **operational priority**."
    )
with right:
    st.image("https://upload.wikimedia.org/wikipedia/commons/1/15/TDCJ_Seal.png", width=110)

# -----------------------------
# Sidebar (settings & examples)
# -----------------------------
with st.sidebar:
    st.header("Settings")
    api_url = st.text_input(
        "Azure Function URL",
        value="http://localhost:7071/api/triage",
        help="Your running triage endpoint.",
    )

    st.markdown("---")
    st.subheader("Quick Examples")
    examples = {
        "Benign help request": {
            "subject": "Question about commissary",
            "body": "Hello, I need help understanding the commissary price list for this month."
        },
        "Suspicious coordination": {
            "subject": "Friday night move",
            "body": "Tell the brothers its on for Friday. Use the kitchen shift for the signal and be ready."
        },
        "Threat to officer": {
            "subject": "Incident with officer",
            "body": "That officer came at me again today. If he does that one more time, I’ll make him regret it."
        },
        "Gang-coded colors": {
            "subject": "Follow up on the plan",
            "body": "Pass the word without names. Everyone wears the same color, you know which one."
        },
        "Self-harm concern": {
            "subject": "Feeling hopeless",
            "body": "I can’t do this anymore. Sometimes I think there’s only one way to stop the pain."
        },
    }
    eg_choice = st.selectbox("Load an example", ["(none)"] + list(examples.keys()))

# -----------------------------
# Input Form
# -----------------------------
with st.form("triage_form"):
    if eg_choice != "(none)":
        preset = examples[eg_choice]
        default_subj, default_body = preset["subject"], preset["body"]
    else:
        default_subj, default_body = "", ""

    subj = st.text_input("Subject", value=default_subj)
    body = st.text_area("Body", value=default_body, height=200)

    submitted = st.form_submit_button("Run Analysis ")

# -----------------------------
# Helper functions
# -----------------------------
SEVERITY_COLOR = {
    0: "gray",
    1: "green",
    2: "green",
    3: "yellow",
    4: "orange",
    5: "orange",
    6: "red",
}

def severity_badge(cat: str, sev: int) -> str:
    css = SEVERITY_COLOR.get(sev, "gray")
    return f'<span class="badge {css}">{cat}: severity {sev}</span>'


def explain_routing(combined_priority: str) -> str:
    mapping = {
        "blocked": "Content flagged by Content Safety as potentially harmful (severity ≥ 4).",
        "high": "Elevated due to negative sentiment and/or GPT rationale including urgency.",
        "medium": "Default operational priority based on GPT classification.",
        "low": "Non-urgent; informational or routine content.",
    }
    return mapping.get(combined_priority, "Routed by default policy.")


def explain_services(resp: dict) -> str:
    parts = []
    # Content Safety
    if resp.get("safety"):
        s = resp["safety"]
        blocked_txt = "blocked" if s.get("blocked") else "not blocked"
        parts.append(
            f"**Azure AI Content Safety** analyzed unsafe categories and severities (0–6). Result: *{blocked_txt}*."
        )
    # Sentiment
    if resp.get("sentiment"):
        se = resp["sentiment"]
        conf = se.get("confidence", {})
        parts.append(
            f"**Azure AI Language – Sentiment** detected *{se.get('sentiment','unknown')}* with confidence (pos: {conf.get('positive',0):.2f}, neu: {conf.get('neutral',0):.2f}, neg: {conf.get('negative',0):.2f})."
        )
    # GPT
    if resp.get("gpt"):
        g = resp["gpt"]
        parts.append(
            f"**Azure OpenAI** produced a classification (priority = *{g.get('priority','unknown')}*) and suggested actions, based on combined safety & sentiment context."
        )
    return "\n\n".join(parts)


def nice_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)

# -----------------------------
# Call API & Render
# -----------------------------
if submitted:
    if not subj.strip() and not body.strip():
        st.warning("Please enter a subject and/or body to analyze.")
    else:
        try:
            with st.spinner("Contacting triage service…"):
                r = requests.post(api_url, json={"subject": subj, "body": body}, timeout=40)
            if r.status_code != 200:
                st.error(f"API returned {r.status_code}: {r.text}")
            else:
                data = r.json()

                # Header summary
                top_l, top_r = st.columns([0.7, 0.3])
                with top_l:
                    st.markdown(
                        f"### Result for **{subj or '(no subject)'}**\n"
                        f"_Analyzed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}_"
                    )
                with top_r:
                    p = (data.get("combined_priority") or "low").lower()
                    st.markdown(
                        f'<div class="priority {p}">Combined Priority: {p.title()}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

                # 3-column cards: Safety / Sentiment / GPT
                c1, c2, c3 = st.columns(3)

                # Safety
                with c1:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.markdown("### Safety")
                    s = data.get("safety", {})
                    st.markdown(
                        f"**Blocked:** {'✅ Yes' if s.get('blocked') else '❌ No'}"
                    )
                    cats = s.get("categories", []) or []
                    if cats:
                        badges = " ".join(
                            [severity_badge(c.get("category","Unknown"), int(c.get("severity",0))) for c in cats]
                        )
                        st.markdown(f'<div class="badges">{badges}</div>', unsafe_allow_html=True)
                    else:
                        st.caption("No categories returned.")
                    st.markdown('</div>', unsafe_allow_html=True)

                # Sentiment
                with c2:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.markdown("### Sentiment")
                    se = data.get("sentiment", {})
                    st.write(f"**Overall:** {se.get('sentiment','unknown').title()}")
                    conf = se.get("confidence", {})
                    st.progress(min(max(float(conf.get("positive",0.0)), 0.0), 1.0), text=f"Positive {conf.get('positive',0):.2f}")
                    st.progress(min(max(float(conf.get("neutral",0.0)), 0.0), 1.0), text=f"Neutral {conf.get('neutral',0):.2f}")
                    st.progress(min(max(float(conf.get("negative",0.0)), 0.0), 1.0), text=f"Negative {conf.get('negative',0):.2f}")
                    st.markdown('</div>', unsafe_allow_html=True)

                # GPT classification
                with c3:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.markdown("### GPT Classification")
                    g = data.get("gpt", {})
                    st.write(f"**Priority (GPT):** {g.get('priority','unknown').title()}")
                    reason = g.get("reason") or ""
                    if reason:
                        st.markdown("**Rationale**")
                        st.markdown(f"> {reason}")
                    actions = g.get("suggested_actions") or []
                    if actions:
                        st.markdown("**Suggested Actions**")
                        # de-duplicate any header echoes present in array
                        cleaned = [a for a in actions if a.strip() and not a.lower().startswith("priority:") and a.strip() != "Actions:" and a.strip() != "Suggested Actions:"]
                        st.markdown("\n".join([f"- {a}" for a in cleaned]))
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

                # Routing & Why
                rr_l, rr_r = st.columns([0.55, 0.45])
                with rr_l:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    route = data.get("routing_hint", "(none)")
                    st.markdown("### Routing Decision")
                    st.write(f"**Route:** {route}")
                    st.caption(explain_routing((data.get("combined_priority") or "").lower()))
                    st.markdown('</div>', unsafe_allow_html=True)
                with rr_r:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.markdown("### Which services did what?")
                    st.markdown(explain_services(data))
                    st.markdown('</div>', unsafe_allow_html=True)

                # Raw JSON (expandable)
                with st.expander("Raw JSON response"):
                    st.code(nice_json(data), language="json")

                # Download artifact
                st.download_button(
                    label="Download JSON",
                    mime="application/json",
                    file_name=f"tdcj_triage_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json",
                    data=nice_json(data).encode("utf-8"),
                )

        except requests.exceptions.RequestException as ex:
            st.error(f"Request error: {ex}")
        except Exception as ex:  # noqa
            st.exception(ex)

# Footer
st.markdown("<div class='hr'></div>", unsafe_allow_html=True)
st.caption(
    "This dashboard calls your local Azure Function `/api/triage`. It uses Azure AI Content Safety for harm categories, Azure AI Language for sentiment, and Azure OpenAI for classification & suggested actions. Policies: block if any category severity ≥ 4; otherwise combine sentiment and GPT rationale for priority.")
