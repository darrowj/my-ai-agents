import requests
import os
from datetime import date, datetime, timezone
from dotenv import load_dotenv

load_dotenv()
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"
TASKS_DB = os.environ["NOTION_TASKS_DB"]

def get_open_tasks():
    headers = {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {
        "filter": {
            "and": [
                {"property": "Done", "checkbox": {"equals": False}},
                {"property": "Quick Capture Box", "formula": {"checkbox": {"equals": False}}},
                {"property": "Due", "date": {"on_or_before": datetime.today().strftime('%Y-%m-%d')}}
            ]
        },
        "page_size": 100
    }
    response = requests.post(
        f"https://api.notion.com/v1/databases/{os.environ['NOTION_TASKS_DB']}/query",
        headers=headers,
        json=payload
    )
    data = response.json()
    print("Notion status:", response.status_code, "| message:", data.get("message", "ok"), "| results:", len(data.get("results", [])))
    tasks = []
    for page in data.get("results", []):
        props = page["properties"]
        for key in ["Name", "Task", "Title"]:
            if key in props:
                parts = props[key].get("title", [])
                if parts:
                    tasks.append(parts[0]["plain_text"])
                    break
    print(f"Fetched {len(tasks)} open tasks from Notion")
    for task in data.get("results", []):
        props = task["properties"]
        name = "(no title)"
        for key in ["Name", "Task", "Title"]:
            parts = props.get(key, {}).get("title", [])
            if parts:
                name = parts[0]["plain_text"]
                break
        due_prop = props.get("Due", {}).get("date")
        due = due_prop["start"] if due_prop else "no due date"
        print(f"  - [{due}] {name}")
    return tasks

def get_google_creds():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds

def get_todays_events():
    from googleapiclient.discovery import build

    creds = get_google_creds()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day,
        timeMax=end_of_day,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = []
    for item in result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date", ""))
        summary = item.get("summary", "(no title)")
        if "T" in start:
            t = datetime.fromisoformat(start).astimezone()
            label = t.strftime("%-I:%M %p")
        else:
            label = "All day"
        events.append(f"{label} – {summary}")

    print(f"Fetched {len(events)} calendar events")
    return events

def build_prompt(events, tasks):
    today = date.today().strftime("%A, %B %d %Y")
    events_text = "\n".join(f"  - {e}" for e in events) if events else "  (none)"
    tasks_text = "\n".join(f"  - {t}" for t in tasks) if tasks else "  (none)"
    return f"""Today is {today}.

HARD CALENDAR BLOCKS — do not schedule anything over these:
{events_text}

My open GTD next actions (things still to do):
{tasks_text}

Context: I am transitioning out of full-time employment on June 15, 2026, with full-time availability starting June 16. No commute or office schedule.

Instructions:
- Calendar blocks are fixed. Build the time-block plan around them, not over them.
- - Cross-reference tasks against calendar blocks. If 'Schedule appt with Carol' is on the task list AND there is already a Carol meeting on the calendar today, treat the task as DONE — do not list it as something still to do.
- Address me directly (use "you", not "Jason").

Give me a focused morning briefing:
1. One-sentence summary of the day
2. The single most important thing to do today
3. A simple time-block plan that respects the calendar blocks above
4. Any conflicts or things not to forget

Output ONLY the final briefing. Do not show reasoning, self-corrections, or second-guessing. No 'Wait:', 'Actually', 'Correction:', or inline edits. Write a clean, final memo. Under 200 words."""

def get_briefing(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"num_gpu": 999}
        }
    )
    return response.json()["response"]

def save_html(briefing_text):
    today = date.today().strftime("%A, %B %d, %Y")
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Morning Briefing – {today}</title>
  <style>
    body {{ font-family: Georgia, serif; max-width: 700px; margin: 60px auto; padding: 0 20px; color: #222; line-height: 1.6; }}
    h1 {{ font-size: 1.4em; border-bottom: 2px solid #333; padding-bottom: 8px; }}
    .date {{ color: #666; font-size: 0.9em; margin-bottom: 24px; }}
    p {{ margin: 12px 0; }}
    strong {{ color: #111; }}
    ul, ol {{ padding-left: 1.4em; }}
    li {{ margin: 6px 0; }}
  </style>
</head>
<body>
  <h1>GTD Morning Briefing</h1>
  <div class="date">{today}</div>
  {briefing_text.replace(chr(10), '<br>')}
</body>
</html>"""
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morning_briefing.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Saved to: {output_path}")

if __name__ == "__main__":
    print("Fetching tasks from Notion...")
    tasks = get_open_tasks()
    print(f"Found {len(tasks)} tasks")
    events = get_todays_events()
    prompt = build_prompt(events, tasks)
    print("\n" + "=" * 50)
    print("GTD MORNING BRIEFING")
    print("=" * 50)
    briefing = get_briefing(prompt)
    save_html(briefing)
    print(briefing)
    print("=" * 50)
