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
    "General Consultation": {"duration_min": 45, "price": 100},
    "Dental Implants and Bridges":{"duration_min":150, "price":1000},
   
}

_timezone = pytz.timezone(CLINIC_TIMEZONE)


def init_calendar(token_file: str, calendar_id: str) -> None:
    global _calendar_service, _calendar_id

    # --- CLOUD PATH RESOLVER ---
    # LiveKit Cloud mounts secrets in /etc/secret/
    cloud_token_path = os.path.join("/etc/secret", os.path.basename(token_file))
    
    # Use cloud path if it exists, otherwise use the local path provided
    final_token_path = cloud_token_path if os.path.exists(cloud_token_path) else token_file
    # ---------------------------

    if not os.path.exists(final_token_path):
        raise RuntimeError(
            f"token.json not found at {final_token_path}. "
            "If deploying to cloud, ensure --secret-mount ./token.json was used."
        )

    creds = Credentials.from_authorized_user_file(
        final_token_path,
        ["https://www.googleapis.com/auth/calendar"],
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    _calendar_service = build("calendar", "v3", credentials=creds)
    _calendar_id = calendar_id


def _require_calendar() -> None:
    if _calendar_service is None or _calendar_id is None:
        raise RuntimeError("Google Calendar not initialized. Call init_calendar() first.")


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
    speciality= ", ".join(DOCTORS.keys())
    services = ", ".join(
        f"{name} (${data['price']}, {data['duration_min']} min)"
        for name, data in SERVICES.items()
    )
    return f"Doctors: {doctors}.Speciality: {speciality} .Services: {services}."


# AVAILABILITY TOOL

@function_tool()
async def check_doctor_availability(
    context: RunContext,
    doctor_name: str,
    start_time: str,
    end_time: str,
) -> bool:
    _require_calendar()

    # 1. helper to ensure google-required 'Z' suffix
    def ensure_rfc3339(ts):
        if not ts.endswith('Z') and '+' not in ts:
            return ts + 'Z'
        return ts

    # 2. fix cases where the LLM sends time without a date (e.g., "10:00:00")
    if "T" not in start_time:
        now_date = datetime.datetime.now(_timezone).strftime("%Y-%m-%d")
        start_time = f"{now_date}T{start_time}"
        end_time = f"{now_date}T{end_time}"

    clean_start = ensure_rfc3339(start_time)
    clean_end = ensure_rfc3339(end_time)

    try:
        events = _calendar_service.events().list(
            calendarId=_calendar_id,
            timeMin=clean_start,
            timeMax=clean_end,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        # 3. conflict Check logic
        for event in events.get("items", []):
            summary = event.get("summary", "").lower()
            # If the doctor's name is in the event
            if doctor_name.lower() in summary or "booked" in summary:
                return False # Slot is NOT available

        return True # Slot IS available
        
    except Exception as e:
        # this prevents the "Internal Error" by catching the crash
        print(f"Calendar API Error: {e}")
        return False



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
