# Azure Email Triage Accelerator (Python Functions)

A clean, minimal accelerator that implements the architecture in your diagram:

- **Exchange/Outlook email** → **Power Automate** → **Azure Function (Python)**
- Function calls **Azure Content Safety**, **Azure AI Language (Sentiment)**, and **Azure OpenAI (GPT‑4o‑mini)**.
- Results are persisted to **Azure Storage (Blob)** and can drive **routing** (Teams/ITSM, Agent queue, Auto‑reply/Archive).
- Comes with a simple **Azure‑branded UI** for local testing.

> Use this repo as a starter for multiple triage use‑cases (IT support, HR, Facilities, Security).

---

## Quick Start (Local)

1. **Install tools**
   - Python 3.10+
   - Azure Functions Core Tools v4
   - Node not required (UI is static HTML)
   - (Optional) **Azurite** for local Blob storage: `npm i -g azurite` then run `azurite`

2. **Clone & create virtual env**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure settings**
   - Copy `local.settings.template.json` to `local.settings.json` and fill in your **endpoints** and **keys**.
   - For local dev, ensure `AzureWebJobsStorage` uses Azurite and `BLOB_ACCOUNT_URL` is `http://127.0.0.1:10000/devstoreaccount1`.

4. **Run Azurite (if local storage)**
   ```bash
   azurite
   ```

5. **Start the Functions host**
   ```bash
   func start
   ```

6. **Open the UI**
   - Open `ui/index.html` in your browser.
   - Enter a sample email and click **Analyze**.
   - Or run the CLI sample: `python scripts/send_sample.py`.

> The HTTP endpoint is `POST http://localhost:7071/api/triage?code=local`

---

## How Scoring & Routing Works

1. **Azure Content Safety** analyzes the body for `Hate`, `Violence`, `Self-harm`, `Sexual`. Any category with severity ≥ 4 sets `blocked=true`.
2. **Azure AI Language (Sentiment)** returns `positive/neutral/negative` with confidences.
3. **Azure OpenAI** classifies **priority** (high/medium/low) and suggests actions with a short rationale.
4. **Combiner**:
   - If `blocked`: `combined_priority = "blocked"` → **Auto-reply/Archive**.
   - Else if **negative** sentiment and GPT mentions urgency or `priority=high`: `combined_priority = "high"` → **Teams + ITSM**.
   - Else fallback to GPT’s priority:
     - `high` → **Teams + ITSM**
     - `medium` → **Agent Queue**
     - `low` → **Auto-reply/Archive**

All results are saved as `{guid}.json` to the `BLOB_CONTAINER` (default `triage-results`).

---

## Power Automate Integration (Prod)

1. **Trigger**: *When a new email arrives in a shared mailbox (V3)* → Filter by folder/rules.
2. **HTTP action**: POST to the Function URL:
   - URL: `https://<functionapp>.azurewebsites.net/api/triage?code=<function_key>`
   - Body (example):
     ```json
     {
       "subject": "@{triggerOutputs()?['body/subject']}",
       "body": "@{triggerOutputs()?['body/bodyPreview']}",
       "sender": "@{triggerOutputs()?['body/from/emailAddress/address']}",
       "importance": "@{triggerOutputs()?['body/importance']}"
     }
     ```
3. **Route** based on `combined_priority`/`routing_hint`:
   - **Teams/ITSM**: Create channel post + create ticket.
   - **Agent Queue**: Add to your queue / Planner / Dataverse table.
   - **Auto-reply**: Send template response & archive.

---

## Azure Resources to Create

- **Function App** (Python 3.10), with **Application Insights**
- **Storage Account** (for Functions + results) – use **Managed Identity** in prod
- **Azure AI Services**:
  - **Azure AI Language** (Text Analytics) with key + endpoint
  - **Azure AI Content Safety** with key + endpoint
  - **Azure OpenAI** with deployment `gpt-4o-mini`
- (Optional) **Key Vault** to store secrets and use Managed Identity

> Set these as application settings in the Function App (same variable names as `local.settings.json`).

---

## Deploy

```bash
# Login & set subscription
az login
az account set --subscription "<SUB_ID>"

# Create storage & function app (example names)
az storage account create -g <rg> -n <stgname> -l <region> --sku Standard_LRS
az functionapp create -g <rg> -n <appname> -s <stgname> --consumption-plan-location <region> --runtime python --runtime-version 3.10

# Deploy from local
func azure functionapp publish <appname>
```

After deploy, set the Function App **Configuration** values (same keys as local).

---

## Optional: Microsoft AI Foundry

- Register the above services as **Connections** in Foundry.
- Create a **project** with:
  - Connection to your Azure OpenAI deployment
  - REST tool to call the Function endpoint for triage
- Use the accelerator as a building block for agent workflows that decide routing or generate replies.

---

## Repo Layout

```
email-triage-accelerator/
├─ src/
│  ├─ common/               # shared models + client helpers + logic
│  └─ function_app/         # Azure Functions (HTTP trigger: /api/triage)
├─ ui/                      # static Azure-branded UI for local testing
├─ scripts/                 # sample POST script
├─ requirements.txt
├─ host.json
├─ local.settings.template.json
└─ README.md
```

---

## Security Notes

- Never commit secrets. Use `local.settings.json` locally and app settings in Azure.
- In production enable CORS to your known domains only (update `host.json`).

---

## Troubleshooting

- **401/403 calling services**: Verify keys/endpoints, region, and API version.
- **Blob write fails** locally: Ensure **Azurite** is running and the URL matches.
- **CORS** from the UI: Confirm Functions host CORS settings (here we allow `*` for local).

Enjoy!
