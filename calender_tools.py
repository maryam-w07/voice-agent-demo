import os
import datetime
import pytz
from typing import Dict, Optional, Any, cast
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource #Google API Client 
from livekit.agents import function_tool, RunContext


CLINIC_TIMEZONE = "Asia/Karachi"

DOCTORS: Dict[str, str] = {
    "general dentistry": "Dr.Badr",
     "Orthodontics": "Dr.jones",
     "Pediatric Dentistry" : "Dr.Ella",
}


SERVICES: Dict[str, Dict[str, int]] = {
    "Cleaning": {"duration_min": 60, "price": 150},
    "Filling": {"duration_min": 90, "price": 300},
    "General Consultation" : {"duration_min":30,"price":2000}
}

_timezone = pytz.timezone(CLINIC_TIMEZONE)


def init_calendar(token_file: str, calendar_id: str) -> None: #google calender api authentication func, implements the OAuth 2.0 
    global _calendar_service, _calendar_id

    if not os.path.exists(token_file): #load credentials from token file
        raise RuntimeError(
            f"token.json not found at {token_file}. "
            "Run OAuth locally once before starting the agent."
        )

    creds = Credentials.from_authorized_user_file(
        token_file,
        ["https://www.googleapis.com/auth/calendar"],
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request()) #refresh the token/automatically get a new token

    _calendar_service = build("calendar", "v3", credentials=creds) #build(serviceName, version, **kwargs),created calender obj #build will return resource
    _calendar_id = calendar_id

    # dynamically create a service object that can communicate with the Google Calendar API
def _require_calendar() -> None:
    if _calendar_service is None or _calendar_id is None:
        raise RuntimeError("Google Calendar not initialized. Call init_calendar() first.")


def _parse_datetime(date: str, time: str) -> datetime.datetime: #google Calendar requires a formal datetime object that includes the time zone (e.g., "2025-12-25 14:30:00+05:00").
    naive = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M") #the user gives the date/time-->llm extracts the metadeta-->function converts to standard
    return _timezone.localize(naive)


@function_tool()
async def list_doctors_and_services(context: RunContext) -> str:
    doctors = ", ".join(DOCTORS.values())
    services = ", ".join(
        f"{name} (${data['price']}, {data['duration_min']} min)"
        for name, data in SERVICES.items()
    )
    return f"Doctors: {doctors}. Services: {services}."


@function_tool()
async def book_appointment(
    context: RunContext,
    patient_name: str,
    patient_phone: str,
    date: str,
    time: str,
    doctor_key: str,
    service_key: str,
) -> str:
    _require_calendar()

    #  match input doctor name to dictionary values
    doctor_input = doctor_key.strip().lower()
    matched_doctor_key = None
    for key, name in DOCTORS.items():
        if doctor_input == name.lower():  # exact case-insensitive match
            matched_doctor_key = key
            break

    if matched_doctor_key is None:
        # allow partial match
        for key, name in DOCTORS.items():
            if doctor_input in name.lower():
                matched_doctor_key = key
                break

    if matched_doctor_key is None:
        return f"Invalid doctor selection. Available doctors: {', '.join(DOCTORS.values())}"

    # Use matched doctor key from here on
    doctor_key = matched_doctor_key

    if service_key not in SERVICES:
        print("invalid service")
        return "Invalid service selection."

    # Calendar event requires Start Time and End Time
    start_dt = _parse_datetime(date, time)  # exact moment appointment begins
    duration = SERVICES[service_key]["duration_min"]  # appointment length
    end_dt = start_dt + datetime.timedelta(minutes=duration)

    event = {
        "summary": f"{service_key.title()} – {DOCTORS[doctor_key]}",
        "description": (
            f"Patient: {patient_name}\n"
            f"Phone: {patient_phone}\n"
            f"Doctor: {DOCTORS[doctor_key]}\n"
            f"Service: {service_key.title()}\n"
            f"Price: ${SERVICES[service_key]['price']}"
        ),
        "visibility": "public",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": CLINIC_TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": CLINIC_TIMEZONE},
    }

    created = _calendar_service.events().insert(
        calendarId=_calendar_id, body=event
    ).execute()

    return (
        f"Appointment confirmed for {patient_name} on {date} at {time} "
        f"with {DOCTORS[doctor_key]}. Your appointment ID is {created['id']}."
    )

    print("SUMMARY FROM API:", created.get("summary"))
    print("Event ID:", created["id"])
    print("Event link:", created.get("htmlLink"))
 


@function_tool()
async def cancel_appointment(context: RunContext, appointment_id: str) -> str:
    _require_calendar()
    try:
        _calendar_service.events().delete(
            calendarId=_calendar_id,
            eventId=appointment_id
        ).execute()
        return "Your appointment has been successfully canceled."
    except Exception:
        return "I could not find an appointment with that ID."
