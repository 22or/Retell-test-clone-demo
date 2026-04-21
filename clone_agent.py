"""
Clone the source Retell agent + conversation flow into a new agent,
and repoint all tool API URLs to our webhook server.

Usage: python3 clone_agent.py [--name "New Agent Name"]
"""

import argparse
import copy
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RETELL_API_KEY")
SOURCE_AGENT_ID = os.getenv("SOURCE_AGENT_ID", "agent_d388c52c6e675de7576f44d4d1")
SOURCE_FLOW_ID = os.getenv("SOURCE_FLOW_ID", "conversation_flow_d64e25f6b250")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.retellai.com"


def get_source_agent() -> dict:
    r = httpx.get(f"{BASE_URL}/get-agent/{SOURCE_AGENT_ID}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_source_flow() -> dict:
    r = httpx.get(f"{BASE_URL}/get-conversation-flow/{SOURCE_FLOW_ID}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# Map original tool name -> our endpoint path
TOOL_ENDPOINT_MAP = {
    "get_availability": "/api/get_availability",
    "book_appointment": "/api/book_appointment",
    "confirm_appt": "/api/confirm_appointment",
}


def repoint_tools(tools: list, base_url: str) -> list:
    """Replace each tool's URL with our server's endpoint."""
    updated = copy.deepcopy(tools)
    for tool in updated:
        name = tool.get("name", "")
        path = TOOL_ENDPOINT_MAP.get(name)
        if path:
            tool["url"] = base_url.rstrip("/") + path
            print(f"  Repointing '{name}' -> {tool['url']}")
    return updated


def create_flow(flow: dict, new_name: str, base_url: str) -> dict:
    tools = repoint_tools(flow.get("tools", []), base_url)
    payload = {
        "nodes": flow["nodes"],
        "global_prompt": flow["global_prompt"],
        "start_speaker": flow["start_speaker"],
        "start_node_id": flow["start_node_id"],
        "tools": tools,
        "components": flow.get("components", []),
        "model_choice": flow.get("model_choice"),
        "tool_call_strict_mode": flow.get("tool_call_strict_mode", False),
        "kb_config": flow.get("kb_config"),
    }
    r = httpx.post(f"{BASE_URL}/create-conversation-flow", headers=HEADERS, json=payload, timeout=30)
    if not r.is_success:
        print("Create flow error:", r.text)
    r.raise_for_status()
    return r.json()


def create_agent(source: dict, new_flow_id: str, new_name: str, base_url: str) -> dict:
    copy_fields = [
        "language", "voice_id", "voice_temperature", "voice_speed", "volume",
        "max_call_duration_ms", "interruption_sensitivity", "normalize_for_speech",
        "begin_message_delay_ms", "allow_user_dtmf", "denoising_mode",
        "data_storage_setting", "timezone", "post_call_analysis_model",
        "pii_config", "handbook_config",
    ]
    payload = {k: source[k] for k in copy_fields if k in source}
    payload["agent_name"] = new_name
    payload["response_engine"] = {
        "type": "conversation-flow",
        "conversation_flow_id": new_flow_id,
    }
    r = httpx.post(f"{BASE_URL}/create-agent", headers=HEADERS, json=payload, timeout=30)
    if not r.is_success:
        print("Create agent error:", r.text)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="Service Appointment Booking (Clone)")
    parser.add_argument("--webhook-url", default=WEBHOOK_BASE_URL,
                        help="Public base URL of your webhook server")
    args = parser.parse_args()

    print(f"Fetching source agent {SOURCE_AGENT_ID}...")
    source_agent = get_source_agent()

    print(f"Fetching source flow {SOURCE_FLOW_ID}...")
    source_flow = get_source_flow()

    print(f"Creating new conversation flow: '{args.name}'...")
    new_flow = create_flow(source_flow, args.name, args.webhook_url)
    new_flow_id = new_flow["conversation_flow_id"]
    print(f"  -> flow created: {new_flow_id}")

    print(f"Creating new agent: '{args.name}'...")
    new_agent = create_agent(source_agent, new_flow_id, args.name, args.webhook_url)
    new_agent_id = new_agent["agent_id"]
    print(f"  -> agent created: {new_agent_id}")

    print("\nAdd to your .env:")
    print(f"  CLONED_AGENT_ID={new_agent_id}")
    print(f"  CLONED_FLOW_ID={new_flow_id}")

    with open(".cloned_ids", "w") as f:
        json.dump({"agent_id": new_agent_id, "flow_id": new_flow_id}, f, indent=2)
    print("Saved to .cloned_ids")


if __name__ == "__main__":
    main()
