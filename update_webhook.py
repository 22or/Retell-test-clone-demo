"""
Point the cloned agent's webhook_url at your running server.
Run after clone_agent.py and after your server is publicly accessible.

Usage: python update_webhook.py --url https://your-server.com
"""

import argparse
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RETELL_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
BASE_URL = "https://api.retellai.com"


def load_cloned_agent_id() -> str:
    agent_id = os.getenv("CLONED_AGENT_ID")
    if not agent_id:
        try:
            with open(".cloned_ids") as f:
                agent_id = json.load(f)["agent_id"]
        except FileNotFoundError:
            raise RuntimeError("Run clone_agent.py first, or set CLONED_AGENT_ID in .env")
    return agent_id


def update_webhook(agent_id: str, webhook_url: str):
    payload = {"webhook_url": webhook_url}
    r = httpx.patch(f"{BASE_URL}/update-agent/{agent_id}", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Public base URL of your webhook server")
    args = parser.parse_args()

    agent_id = load_cloned_agent_id()
    webhook_url = args.url.rstrip("/") + "/webhook"

    print(f"Updating agent {agent_id} -> {webhook_url}")
    result = update_webhook(agent_id, webhook_url)
    print("Updated:", result.get("agent_id"), "webhook_url:", result.get("webhook_url"))


if __name__ == "__main__":
    main()
