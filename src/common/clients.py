import os
import json
import datetime
from typing import Dict, Any

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from azure.ai.textanalytics import TextAnalyticsClient
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory

from openai import AzureOpenAI
import httpx


def load_settings() -> Dict[str, Any]:
    return {
        "openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "openai_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "openai_deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
        "openai_api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),

        "cs_endpoint": os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT"),
        "cs_key": os.getenv("AZURE_CONTENT_SAFETY_KEY"),

        "lang_endpoint": os.getenv("AZURE_AI_LANGUAGE_ENDPOINT"),
        "lang_key": os.getenv("AZURE_AI_LANGUAGE_KEY"),

        "storage_conn_str": os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        "blob_account_url": os.getenv("BLOB_ACCOUNT_URL"),
        "blob_container": os.getenv("BLOB_CONTAINER", "triage-results"),
    }


# ---------- Azure Clients ----------

def make_text_analytics_client(s: Dict[str, Any]) -> TextAnalyticsClient:
    return TextAnalyticsClient(
        endpoint=s["lang_endpoint"],
        credential=AzureKeyCredential(s["lang_key"])
    )


def make_content_safety_client(s: Dict[str, Any]) -> ContentSafetyClient:
    return ContentSafetyClient(
        endpoint=s["cs_endpoint"],
        credential=AzureKeyCredential(s["cs_key"])
    )


def make_openai_client(s: Dict[str, Any]) -> AzureOpenAI:
    """
    Azure OpenAI client that disables proxy inheritance (fixes 'proxies' kwarg error).
    """
    # ✅ Remove proxy-related environment variables before client init
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "all_proxy"):
        if k in os.environ:
            os.environ.pop(k)

    # ✅ Create httpx client with proxy/env disabled
    http_client = httpx.Client(trust_env=False, timeout=60.0)

    # ✅ Initialize AzureOpenAI cleanly
    return AzureOpenAI(
        api_key=s["openai_key"],
        api_version=s["openai_api_version"],
        azure_endpoint=s["openai_endpoint"],
        http_client=http_client
    )


def make_blob_client(s: Dict[str, Any]) -> BlobServiceClient:
    """
    Prefer local Azurite connection string; fallback to real Azure credentials if not available.
    """
    conn = s.get("storage_conn_str")
    if conn:
        return BlobServiceClient.from_connection_string(conn)

    url = s.get("blob_account_url")
    if not url:
        raise ValueError("No storage connection string or account URL provided.")
    cred = DefaultAzureCredential()
    return BlobServiceClient(account_url=url, credential=cred)


# ---------- Helpers ----------

def ensure_container(blob_svc: BlobServiceClient, name: str) -> None:
    try:
        blob_svc.create_container(name)
    except Exception:
        pass  # Container probably already exists


def write_json(blob_svc: BlobServiceClient, container: str, name: str, payload: dict) -> None:
    ensure_container(blob_svc, container)
    blob = blob_svc.get_blob_client(container, name)
    blob.upload_blob(json.dumps(payload, indent=2).encode("utf-8"), overwrite=True)


def now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
