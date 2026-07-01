import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

job = {"route": "London -> Manchester", "cargo": "furniture", "price": 450}

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

if "YES" in decision:
    print("Ok - send a notification")
else:
    print("Skipped")