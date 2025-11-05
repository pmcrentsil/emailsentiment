import json, requests

payload = {
  "subject": "Cannot access VPN",
  "body": "My VPN keeps disconnecting every 2 minutes since the update. Need help urgently.",
  "sender": "alex@contoso.com",
  "importance": "High"
}
r = requests.post("http://localhost:7071/api/triage?code=local", json=payload, timeout=60)
print(r.status_code)
print(r.text)
