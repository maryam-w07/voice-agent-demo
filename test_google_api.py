from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import datetime

# -----------------------
# CONFIG
# -----------------------
TOKEN_FILE = "token.json"
CALENDAR_ID = "1d2d18d6223550642fd1a340fcb768f63cfe63ea5b72776931c5e4a2711abd12@group.calendar.google.com"


# -----------------------
# AUTH
# -----------------------
creds = Credentials.from_authorized_user_file(
    TOKEN_FILE,
    ["https://www.googleapis.com/auth/calendar"]
)

service = build("calendar", "v3", credentials=creds)

# -----------------------
# EVENT DATA
# -----------------------
start_time = datetime.datetime.now() + datetime.timedelta(hours=1)
end_time = start_time + datetime.timedelta(minutes=45)

event = {
    "summary": "Test Appointment",
    "description": "This is a test event created via Google Calendar API",
    "start": {
        "dateTime": start_time.isoformat(),
        "timeZone": "Asia/Karachi",
    },
    "end": {
        "dateTime": end_time.isoformat(),
        "timeZone": "Asia/Karachi",
    },
}

# -----------------------
# CREATE EVENT
# -----------------------
created_event = service.events().insert(
    calendarId=CALENDAR_ID,
    body=event
).execute()

print(" Event created successfully!")
print("SUMMARY FROM API:", created_event.get("summary"))
print("Event ID:", created_event["id"])
print("Event link:", created_event.get("htmlLink"))
