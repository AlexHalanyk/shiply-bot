import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")

url = f"https://api.telegram.org/bot{token}/sendMessage"
data = {"chat_id": chat_id, "text": "Hello from Shiply-bot 🚚"}
response = requests.post(url, data=data)

print(response.status_code)