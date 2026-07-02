import os
import requests
from dotenv import load_dotenv
from google import genai
import sqlite3

load_dotenv()
token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

db = sqlite3.connect("data/sent_jobs.db")
db_cursor = db.cursor()

db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS sent_jobs (
        link TEXT PRIMARY KEY
    )
""")

def send_notification(job):
    text = f"🚚  New Order\n{job['route']}\nPrice: £{job['price']}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
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