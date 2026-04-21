"""
Webhook server for the cloned Retell service agent.

Retell calls each tool endpoint directly via HTTP (URL configured per-tool).
get_availability: GET /api/get_availability  (headers: intent)
book_appointment: POST /api/book_appointment (form: time, ...)
confirm_appointment: POST /api/confirm_appointment (form: name, phone_number)
"""

import logging
import os
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, Form, Header, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Retell Service Agent API")

# ---------------------------------------------------------------------------
# In-memory appointment store — swap with your DB / calendar integration
# ---------------------------------------------------------------------------
APPOINTMENTS: dict[str, dict] = {}

MOCK_SLOTS = [
    {"day": "Monday",    "date": "2026-04-27", "time": "9:00 AM"},
    {"day": "Monday",    "date": "2026-04-27", "time": "11:00 AM"},
    {"day": "Tuesday",   "date": "2026-04-28", "time": "2:00 PM"},
    {"day": "Wednesday", "date": "2026-04-29", "time": "10:00 AM"},
    {"day": "Thursday",  "date": "2026-04-30", "time": "3:30 PM"},
    {"day": "Friday",    "date": "2026-05-01", "time": "8:00 AM"},
]


# ---------------------------------------------------------------------------
# Tool endpoints
# ---------------------------------------------------------------------------

@app.get("/api/get_availability")
async def get_availability(intent: Optional[str] = Header(None)):
    """Called by 'get_availability' tool (GET, intent passed in header)."""
    log.info("get_availability | intent=%s", intent)

    slots = MOCK_SLOTS
    if intent and "modify" in intent.lower():
        # For modifications show more slots
        slots = MOCK_SLOTS

    lines = [f"{s['day']} {s['date']} at {s['time']}" for s in slots[:4]]
    return {"available_slots": lines, "message": "Here are the next available appointments: " + "; ".join(lines)}


@app.post("/api/book_appointment")
async def book_appointment(
    request: Request,
    time: Optional[str] = Form(None),
):
    """Called by 'book_appointment' tool (POST form)."""
    # Retell may send additional variables via form; read all form data
    form = await request.form()
    data = dict(form)
    log.info("book_appointment | %s", data)

    appt_time = time or data.get("time", "TBD")
    name = data.get("name", data.get("caller_name", "Guest"))
    phone = data.get("phone_number", data.get("user_number", "unknown"))
    vehicle = data.get("vehicle", data.get("vehicle_info", "Unknown vehicle"))
    service = data.get("service_type", data.get("service", "General Service"))

    appt_id = f"APT-{len(APPOINTMENTS) + 1001}"
    APPOINTMENTS[phone] = {
        "id": appt_id,
        "name": name,
        "phone": phone,
        "vehicle": vehicle,
        "service": service,
        "time": appt_time,
        "created_at": datetime.utcnow().isoformat(),
    }
    log.info("Booked: %s", APPOINTMENTS[phone])

    return {
        "success": True,
        "confirmation_number": appt_id,
        "message": (
            f"Appointment confirmed. Confirmation number {appt_id}. "
            f"{name} is booked for {service} at {appt_time}. "
            "We will send a reminder before your appointment."
        ),
    }


@app.post("/api/confirm_appointment")
async def confirm_appointment(
    request: Request,
    name: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
):
    """Called by 'confirm_appt' tool (POST form)."""
    form = await request.form()
    data = dict(form)
    log.info("confirm_appointment | %s", data)

    caller_name = name or data.get("name", "")
    phone = phone_number or data.get("phone_number", data.get("user_number", ""))

    appt = APPOINTMENTS.get(phone)
    if not appt:
        return {
            "found": False,
            "message": f"No appointment found for {phone}. Please double-check or call to schedule.",
        }

    return {
        "found": True,
        "confirmation_number": appt["id"],
        "message": (
            f"Appointment {appt['id']} confirmed for {appt['name']}: "
            f"{appt['service']} at {appt['time']} for a {appt['vehicle']}."
        ),
    }


# ---------------------------------------------------------------------------
# Health / admin
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "appointment_count": len(APPOINTMENTS)}


@app.get("/appointments")
async def list_appointments():
    return {"appointments": list(APPOINTMENTS.values())}


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
