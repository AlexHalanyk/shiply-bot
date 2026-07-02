import os
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


def send_notification(job):
    text = f"🚚  New Order\n{job['route']}\nPrice: £{job['price']}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    subscribers = get_subscribers()
    for subscriber_id in subscribers:
        data = {"chat_id": subscriber_id, "text": text}
        requests.post(url, data=data)

def is_relevant_ai(job):
    prompt = f"""You are helping a UK transport driver decide if a delivery job is worth taking.

The driver's criteria for a good job:
- Price of £200 or more is acceptable
- Longer intercity routes are fine if the price matches
- Any standard cargo (furniture, boxes, appliances) is fine

Job details:
Route: {job['route']}
Cargo: {job['cargo']}
Price: £{job['price']}

Based on the criteria above, answer with only one word: YES if the job is worth taking, NO if it is not."""

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

def check_new_subscribers():
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url)
    data = response.json()

    last_update_id = 0
    for update in data["result"]:
        message = update.get("message", {})
        chat = message.get("chat", {})
        new_chat_id = chat.get("id")
        if new_chat_id is not None:
            add_subscriber(new_chat_id)
            print("New subscriber:", new_chat_id)
        last_update_id = update["update_id"]

    if last_update_id != 0:
        requests.get(url, params={"offset": last_update_id + 1})