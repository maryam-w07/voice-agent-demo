import os
import datetime
import pytz
from typing import Dict, Optional, Any, cast
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource
from livekit.agents import function_tool, RunContext


CLINIC_TIMEZONE = "Asia/Karachi"


DOCTORS: Dict[str, str] = {
    "general dentistry": "Dr.Badr",
    "Orthodontics": "Dr.jones",
    "Pediatric Dentistry": "Dr.Ella",
}


SERVICES: Dict[str, Dict[str, int]] = {
    "Cleaning": {"duration_min": 60, "price": 150},
    "Fillings and Crowns": {"duration_min": 90, "price": 500},
    "General Consultation": {"duration_min": 30, "price": 100},
    "Dental Implants and Bridges":{"duration_min":10, "price":1000},
   
}


_timezone = pytz.timezone(CLINIC_TIMEZONE)


#calender initialization & authentication method
def init_calendar(token_file: str, calendar_id: str) -> None:
    global _calendar_service, _calendar_id

    if not os.path.exists(token_file):
        raise RuntimeError(
            f"token.json not found at {token_file}. "
            "Run OAuth locally once before starting the agent."
        )

    creds = Credentials.from_authorized_user_file(
        token_file,
        ["https://www.googleapis.com/auth/calendar"],
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    _calendar_service = build("calendar", "v3", credentials=creds)
    _calendar_id = calendar_id


def _require_calendar() -> None:
    if _calendar_service is None or _calendar_id is None:
        raise RuntimeError("Google Calendar not initialized. Call init_calendar() first.")
        

#current datetime extraction nd formatting method
def _parse_datetime(date: str, time: str) -> datetime.datetime:
    now = datetime.datetime.now()

    # If year is missing, inject current year
    if len(date.split("-")) == 2:  # e.g. "12-19"
        date = f"{now.year}-{date}"

    naive = datetime.datetime.strptime(
        f"{date} {time}",
        "%Y-%m-%d %H:%M"
    )

    if naive < now:
        raise ValueError("Appointment time must be in the future.")

    return _timezone.localize(naive)


@function_tool()
async def current_time_date(context: RunContext) -> str: #livekit tools shouldnt return python objects, not JSON-serializable
    now = datetime.datetime.now(_timezone)
    return now.isoformat()


@function_tool()
async def list_doctors_and_services(context: RunContext) -> str:
    doctors = ", ".join(DOCTORS.values())
    services = ", ".join(
        f"{name} (${data['price']}, {data['duration_min']} min)"
        for name, data in SERVICES.items()
    )
    return f"Doctors: {doctors}. Services: {services}."


# AVAILABILITY TOOL
@function_tool()
async def check_doctor_availability(
    context: RunContext,
    doctor_name: str,
    start_time: str,
    end_time: str,
) -> bool:
    _require_calendar()

    events = _calendar_service.events().list(
        calendarId=_calendar_id,
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    for event in events.get("items", []):
        if doctor_name.lower() in event.get("summary", "").lower():
            return False

    return True


# BOOK APPOINTMENT 
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

    # match input doctor name to dictionary values
    doctor_input = doctor_key.strip().lower()
    matched_doctor_key = None

    for key, name in DOCTORS.items():
        if doctor_input == name.lower():
            matched_doctor_key = key
            break

    if matched_doctor_key is None:
        for key, name in DOCTORS.items():
            if doctor_input in name.lower():
                matched_doctor_key = key
                break

    if matched_doctor_key is None:
        return f"Invalid doctor selection. Available doctors: {', '.join(DOCTORS.values())}"

    doctor_key = matched_doctor_key

    if service_key not in SERVICES:
        return "Invalid service selection."

    start_dt = _parse_datetime(date, time)
    duration = SERVICES[service_key]["duration_min"]
    end_dt = start_dt + datetime.timedelta(minutes=duration)

    # AVAILABILITY CHECK
    is_available = await check_doctor_availability(
        context,
        DOCTORS[doctor_key],
        start_dt.isoformat(),
        end_dt.isoformat(),
    )

    if not is_available:
        return f"{DOCTORS[doctor_key]} is not available at this time. Please choose another slot."

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
