import os
import re
import requests
from dotenv import load_dotenv
from google import genai
import sqlite3

load_dotenv()
token = os.getenv("TELEGRAM_TOKEN")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

db = sqlite3.connect("data/sent_jobs.db")
db_cursor = db.cursor()

db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS sent_jobs (
        link TEXT PRIMARY KEY
    )
""")

db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscribers (
        chat_id INTEGER PRIMARY KEY
    )
""")

db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        slug TEXT PRIMARY KEY
    )
""")

db_cursor.execute("SELECT COUNT(*) FROM companies")
if db_cursor.fetchone()[0] == 0:
    db_cursor.executemany(
        "INSERT INTO companies (slug) VALUES (?)", [("skyscanner",), ("monzo",)]
    )
    db.commit()

GREENHOUSE_SLUG_RE = re.compile(r"greenhouse\.io/(?:v1/boards/)?([a-zA-Z0-9-]+)")
BARE_SLUG_RE = re.compile(r"[a-zA-Z0-9-]+")


def extract_greenhouse_slug(text):
    match = GREENHOUSE_SLUG_RE.search(text)
    if match:
        return match.group(1)
    if BARE_SLUG_RE.fullmatch(text):
        return text
    return None


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})


def send_notification(job):
    text = f"💼  New Job\n{job['title']} at {job['company']}\n{job['location']}\n{job['link']}"
    for subscriber_id in get_subscribers():
        send_message(subscriber_id, text)

def is_relevant_ai(job):
    prompt = f"""You are helping a UK computer science graduate find a suitable first software engineering job.

Job details:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}

Is this a graduate or junior software engineering role in the UK suitable for a CS graduate?
Answer with only one word: YES or NO."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    decision = response.text.strip().upper()
    return "YES" in decision

def already_sent(link):
    db_cursor.execute("SELECT link FROM sent_jobs WHERE link = ?", (link,))
    return db_cursor.fetchone() is not None


def mark_as_sent(link):
    db_cursor.execute("INSERT OR IGNORE INTO sent_jobs (link) VALUES (?)", (link,))
    db.commit()

def add_subscriber(chat_id):
    db_cursor.execute("INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)", (chat_id,))
    db.commit()


def get_subscribers():
    db_cursor.execute("SELECT chat_id FROM subscribers")
    rows = db_cursor.fetchall()
    return [row[0] for row in rows]


def add_company(slug):
    db_cursor.execute("INSERT OR IGNORE INTO companies (slug) VALUES (?)", (slug,))
    db.commit()


def get_companies():
    db_cursor.execute("SELECT slug FROM companies")
    return [row[0] for row in db_cursor.fetchall()]


def is_valid_greenhouse_board(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        return False
    return response.status_code == 200


def check_incoming_messages():
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url)
    data = response.json()

    last_update_id = 0
    for update in data["result"]:
        message = update.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "").strip()

        if chat_id is not None:
            if text == "/start":
                add_subscriber(chat_id)
                print("New subscriber:", chat_id)
            else:
                slug = extract_greenhouse_slug(text)
                if slug is not None:
                    if is_valid_greenhouse_board(slug):
                        add_company(slug)
                        send_message(chat_id, f"✅ {slug} added, now tracking")
                        print("New company tracked:", slug)
                    else:
                        send_message(chat_id, f"❌ Board not found: {slug}")

        last_update_id = update["update_id"]

    if last_update_id != 0:
        requests.get(url, params={"offset": last_update_id + 1})