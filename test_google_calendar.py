import os
from datetime import datetime, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def get_todays_events():
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day,
        timeMax=end_of_day,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    if not events:
        print("No events found for today.")
        return []

    print(f"Found {len(events)} event(s) today:\n")
    results = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        summary = event.get("summary", "(no title)")
        print(f"  - {start}: {summary}")
        results.append(f"{start}: {summary}")

    return results

if __name__ == "__main__":
    print("Testing Google Calendar connection...")
    print("=" * 50)
    get_todays_events()
    print("=" * 50)
