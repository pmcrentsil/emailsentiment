# TDCJ Secure Mail AI – Azure AI Email Triage Accelerator

A production‑ready accelerator that classifies inmate email content for **safety**, **sentiment**, and **operational priority**, and then routes actions.  
It uses **Azure AI Content Safety**, **Azure AI Language (Sentiment)**, **Azure OpenAI**, and **Azure Storage (Blob/Azurite)** behind an **Azure Functions** API, with an optional **Streamlit UI** for analyst review.

---

## ✨ What you get

- **/api/triage** HTTP Function: accepts `{ subject, body }`, returns JSON with safety categories, sentiment, GPT rationale, combined priority, routing hint, and metadata.
- **Streamlit UI** (`ui/app.py`): a clean dashboard titled **“TDCJ – AI Email Sentiment Analysis”** to test and visualize results.
- **Blob/Azurite** archival of every decision as JSON for audit / analytics.
- Clear knobs to tune **severity thresholds, priority rules, prompts, and scoring**.
- Guidance to integrate with **Power Automate** (ingest Outlook email → call Function → conditional routing/blocking).

---

## 🧩 Architecture Overview

```
   Outlook / Email Source
            │
            ▼
   Power Automate (optional) ─────────────┐
            │                             │
            ▼                             │
      Azure Functions  /api/triage  ◀─────┘  (also called by Streamlit UI)
            │
            ├─► Content Safety (harm categories & severities 0–6)
            ├─► Azure AI Language (Sentiment: pos/neu/neg + confidence)
            ├─► Azure OpenAI (priority + rationale + suggested actions)
            │
            └─► Blob Storage / Azurite (JSON audit)
                         │
                         └─► Downstream routing (e.g., Security Review, Agent Queue, Auto‑archive)
```

**Role of the Function App:** It orchestrates all calls, merges results, applies policy logic, and produces a final decision JSON.

---

## 📦 Repository Layout

```
email-triage-accelerator/
├─ triage/__init__.py            # Azure Function entrypoint (HTTP trigger /api/triage)
├─ src/
│  └─ common/
│     ├─ clients.py              # Creates SDK clients (OpenAI, Content Safety, Text Analytics, Blob/Azurite)
│     ├─ logic.py                # Decision logic: thresholds, combining priority, routing
│     └─ models.py               # Pydantic models for structured input/output
├─ ui/
│  └─ app.py                     # Streamlit UI for interactive testing
├─ local.settings.json           # Local dev settings for the Function runtime
├─ requirements.txt              # Python deps
└─ README.md                     # This file
```

---

## ✅ Prerequisites

- **Python 3.11+** and **virtualenv** (or venv)
- **Azure Functions Core Tools v4**
- **Node.js** (if using `npx` to run Azurite) or **Azurite** installed globally
- Azure resources (endpoints & keys) for:
  - **Azure OpenAI**
  - **Azure AI Content Safety**
  - **Azure AI Language (Text Analytics)**
- Optional (local dev storage): **Azurite**

---

## ⚙️ Configuration (local.settings.json)

Create/verify `local.settings.json` (kept **local only**, **do not commit secrets**):

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",

    "PYTHONPATH": "src",

    "AZURE_OPENAI_ENDPOINT": "https://<your-aoai>.openai.azure.com",
    "AZURE_OPENAI_API_KEY": "<your-aoai-key>",
    "AZURE_OPENAI_API_VERSION": "2024-08-01-preview",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-4o-mini",

    "AZURE_CONTENT_SAFETY_ENDPOINT": "https://<your-cs>.cognitiveservices.azure.com/",
    "AZURE_CONTENT_SAFETY_KEY": "<your-cs-key>",

    "AZURE_AI_LANGUAGE_ENDPOINT": "https://<your-lang>.cognitiveservices.azure.com/",
    "AZURE_AI_LANGUAGE_KEY": "<your-lang-key>",

    // Local dev storage – prefer this with Azurite:
    "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",

    // Fallback (used only if connection string isn't present):
    "BLOB_ACCOUNT_URL": "http://127.0.0.1:10000/devstoreaccount1",
    "BLOB_CONTAINER": "triage-results",

    // Optional: leave empty for local
    "APPINSIGHTS_CONNECTION_STRING": ""
  }
}
```

> **Production swap:** set `AZURE_STORAGE_CONNECTION_STRING` to the **real** storage account connection string, and remove the dev `UseDevelopmentStorage=true`. Keep `BLOB_CONTAINER` the same or change as needed.

---

## 🧪 Running Locally

### 1) Start Azurite (local Blob)

- If installed via npm:
  ```bash
  npx azurite --silent --location .azurite --debug ./azurite_debug.log
  ```
- Or if you have the Azurite extension in VS Code, click **Start** from the extension.

> The function uses `AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true` to talk to Azurite.

### 2) Create and activate the virtualenv

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

### 3) Start the Azure Function (HTTP API)

```powershell
func start
```

You should see:
```
Functions:
    triage: [POST] http://localhost:7071/api/triage
```

### 4) Test from a separate terminal (PowerShell)

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:7071/api/triage" `
  -ContentType "application/json" `
  -Body '{
    "subject": "Question about my invoice",
    "body": "Hi team, my invoice #12345 has a duplicate line item. Can you help?"
  }'
```

### 5) Start the Streamlit UI

```powershell
# From repo root
.\.venv\Scripts\Activate
streamlit run ui/app.py
```

Open the URL shown (usually http://localhost:8501). Set **Azure Function URL** to `http://localhost:7071/api/triage`.

---

## 🧠 How the Decisioning Works

- **Content Safety** returns category severities (0–6) across: `Hate`, `Violence`, `SelfHarm`, `Sexual`.
- **Sentiment** returns overall sentiment and confidence scores (pos/neu/neg).
- **Azure OpenAI** returns a **priority** (`high|medium|low`) with a **rationale** and **suggested actions**.

**Policy in `src/common/logic.py`:**

- If **any** Content Safety category severity ≥ **4** → `blocked` (wins).
- Else, if **sentiment** is negative **and** GPT rationale implies urgency → `high`.
- Otherwise → use GPT’s priority (`medium|low`).

It also maps the final **priority → routing hint**:
- `blocked` → **Security Review / Intelligence Unit** (or Auto‑reply/Archive as configured)
- `high` → **Teams + ITSM Ticket**
- `medium` → **Agent Queue**
- `low` → **Auto‑reply / Archive**

> Tune thresholds and routing in `logic.py`. Adjust GPT prompt style/criteria in the triage function where the chat completion is created.

---

## 🔧 Tuning & Customization

### Severity Thresholds
In `src/common/logic.py` (`map_safety` & `combine_priority`), change the block threshold (currently `>= 4`).

### Priority Heuristics
Modify `combine_priority(...)` to incorporate more rules (e.g., certain phrases, sender reputation, or repeated patterns).

### Routing
Change `routing_hint(priority)` to map to your org’s queues, teams, and tickets.

### GPT Prompt
Adjust the prompt (in the function that calls Azure OpenAI) to improve rationale and action suggestions for your domain (e.g., corrections intelligence).

---

## 🖥️ Streamlit UI (ui/app.py)

- Text inputs for **Subject** and **Body**
- Calls the local **Function URL** (configurable in the sidebar)
- Displays **Safety**, **Sentiment**, **GPT** cards
- Shows **Combined Priority**, **Routing Decision**, and **“Which services did what?”**
- Can **download** the raw JSON for record keeping

> The UI is a demo console for analysts; production integrations typically rely on Power Automate or service-to-service calls to the Function.

---

## 🔗 Power Automate Integration (Outlook → Function → Actions)

1. **Trigger**: “When a new email arrives” (Outlook 365).
2. **HTTP Action**: POST to your Function endpoint `/api/triage` with JSON:
   ```json
   {
     "subject": "@{triggerOutputs()?['body/subject']}",
     "body": "@{triggerOutputs()?['body/bodyPreview']}"
   }
   ```
3. **Parse JSON**: Use the Function’s response schema.
4. **Condition** on `combined_priority` or `safety.blocked`:
   - If **blocked**:
     - Move email to restricted folder, or
     - Notify Security/Intel channel, or
     - Auto-reply with a policy notice
   - If **high**: create **ITSM ticket** + Teams alert
   - If **medium**: send to **Agent Queue**
   - If **low**: **archive** or label

> For production, secure the Function with **function keys**/AAD and store secrets in **Key Vault**.

---

## 🗄️ Storage: Azurite → Production Blob

- **Local dev**: `AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true` → saves results into Azurite.
- **Production**: set `AZURE_STORAGE_CONNECTION_STRING` to your real Storage account connection string and deploy.  
  The code will create the container (`triage-results`) if it does not exist.

Optional: Use **Managed Identity** (no secrets in config). In `clients.py`, the Blob client already supports `DefaultAzureCredential()` when `BLOB_ACCOUNT_URL` is used instead of a connection string.

---

## 🚀 Deployment (high-level)

- Provision: Function App, Storage Account, App Insights, Azure OpenAI, Content Safety, Language.
- Configure **App Settings** in the Function App (mirror `local.settings.json` values without secrets in code).
- Deploy code (e.g., `func azure functionapp publish <YourFunctionAppName>`).
- Swap Streamlit for a gated internal UI or Power Automate for full automation.

---

## 🧯 Troubleshooting

**`AuthorizationFailure` talking to Azurite`**  
Use `AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true` instead of only `BLOB_ACCOUNT_URL` during local dev.

**`Client.__init__() got an unexpected keyword argument 'proxies'`**  
Ensure you’re using the latest `openai` Python SDK. Remove any custom `proxies` injection when constructing `AzureOpenAI`.

**Function returns 500**  
Check the Functions console logs. Common causes:
- Missing/incorrect endpoints or keys.
- Azurite not running while using `UseDevelopmentStorage=true`.
- JSON input missing required fields.

**Streamlit: “File does not exist: ui/app.py”**  
Run `streamlit run ui/app.py` **from the repository root**, or fix the path.

---

## 🔐 Security Notes

- Don’t commit keys. Use **Key Vault** and reference secrets in app settings.
- Consider **VNET integration**, **Private Endpoints**, and **Managed Identity**.
- Add **role‑based routing**, **auditing**, and **tamper‑evident storage** for compliance needs.

---

## 📜 License & Attribution

This accelerator demonstrates a pattern for corrections/intelligence triage. Verify and adapt to your jurisdiction’s legal and policy requirements.

---

## 🙋 Support

If you run into issues, capture:
- Function console logs
- The HTTP status and response body from the UI or Power Automate
- Your current `local.settings.json` (redact secrets)

Then reproduce with a minimal test payload and iterate.