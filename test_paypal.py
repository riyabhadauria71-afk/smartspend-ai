import os

import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("PAYPAL_CLIENT_ID", "")
secret = os.getenv("PAYPAL_CLIENT_SECRET", "")
base_url = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")

placeholders = {"", "your_sandbox_client_id", "your_sandbox_client_secret"}
if client_id in placeholders or secret in placeholders:
    raise SystemExit("PayPal credentials are missing in .env")

if "sandbox" not in base_url:
    raise SystemExit("PAYPAL_BASE_URL must be the sandbox address for this project")

try:
    resp = requests.post(
        f"{base_url}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
        timeout=20,
    )
except requests.RequestException as exc:
    raise SystemExit(f"Could not reach PayPal: {exc.__class__.__name__}")

print("HTTP status:", resp.status_code)

if resp.ok:
    data = resp.json()
    print("Token type:", data.get("token_type"))
    print("Expires in (seconds):", data.get("expires_in"))
    print("SUCCESS: your sandbox credentials work.")
else:
    print("FAILED:", resp.text[:300])