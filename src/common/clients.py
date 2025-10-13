import os, json, datetime
from typing import Dict, Any
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.ai.textanalytics import TextAnalyticsClient, AzureKeyCredential
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from openai import AzureOpenAI

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
        "blob_account_url": os.getenv("BLOB_ACCOUNT_URL"),
        "blob_container": os.getenv("BLOB_CONTAINER", "triage-results"),
    }

def make_text_analytics_client(s: Dict[str, Any]) -> TextAnalyticsClient:
    return TextAnalyticsClient(endpoint=s["lang_endpoint"], credential=AzureKeyCredential(s["lang_key"]))

def make_content_safety_client(s: Dict[str, Any]) -> ContentSafetyClient:
    return ContentSafetyClient(endpoint=s["cs_endpoint"], credential=AzureKeyCredential(s["cs_key"]))

def make_openai_client(s: Dict[str, Any]) -> AzureOpenAI:
    return AzureOpenAI(api_key=s["openai_key"], api_version=s["openai_api_version"], azure_endpoint=s["openai_endpoint"])

def make_blob_client(s: Dict[str, Any]) -> BlobServiceClient:
    url = s["blob_account_url"]
    if url and "127.0.0.1" in url:
        return BlobServiceClient(account_url=url)
    cred = DefaultAzureCredential()
    return BlobServiceClient(account_url=url, credential=cred)

def ensure_container(blob_svc: BlobServiceClient, name: str):
    try:
        blob_svc.create_container(name)
    except Exception:
        pass

def write_json(blob_svc: BlobServiceClient, container: str, name: str, payload: dict):
    ensure_container(blob_svc, container)
    blob = blob_svc.get_blob_client(container, name)
    blob.upload_blob(json.dumps(payload, indent=2).encode("utf-8"), overwrite=True)

def now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
