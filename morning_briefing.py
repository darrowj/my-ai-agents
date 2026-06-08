import requests
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5-coder-gpu"
TASKS_DB = os.environ["NOTION_TASKS_DB"]

def get_open_tasks():
    headers = {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"https://api.notion.com/v1/databases/{os.environ['NOTION_TASKS_DB']}/query",
        headers=headers,
        json={"page_size": 15}
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
    return tasks

def get_todays_events():
    return [
        "10:00am - 11:00am: Review notes from Strategy and Networking Event",
        "All day reminder: Enter doc info in MyChart",
    ]

def build_prompt(events, tasks):
    today = date.today().strftime("%A, %B %d %Y")
    events_text = "\n".join(f"  - {e}" for e in events)
    tasks_text = "\n".join(f"  - {t}" for t in tasks)
    return f"""Today is {today}.

My calendar events today:
{events_text}

My open GTD next actions:
{tasks_text}

Give me a focused morning briefing. Include:
1. A one-sentence summary of the day
2. The single most important thing to do today
3. A suggested time-block plan for the day (keep it simple)
4. Any conflicts or things I should not forget

Be direct. Under 200 words."""

def get_briefing(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False, "think": False}
    )
    return response.json()["response"]

if __name__ == "__main__":
    print("Fetching tasks from Notion...")
    tasks = get_open_tasks()
    print(f"Found {len(tasks)} tasks")
    events = get_todays_events()
    prompt = build_prompt(events, tasks)
    print("\n" + "=" * 50)
    print("GTD MORNING BRIEFING")
    print("=" * 50)
    print(get_briefing(prompt))
    print("=" * 50)
