from bot import send_notification, is_relevant_ai, already_sent, mark_as_sent, check_new_subscribers
import time


def is_relevant(job):
    return job["price"] >= 200


jobs = [
    {"route": "London -> Manchester", "cargo": "furniture", "price": 450, "link": "https://example.com/job/1"},
    {"route": "Leeds -> Bristol", "cargo": "boxes", "price": 120, "link": "https://example.com/job/2"},
    {"route": "Glasgow -> London", "cargo": "piano", "price": 600, "link": "https://example.com/job/3"}
]


def check_jobs():
    for job in jobs:
        if already_sent(job["link"]):
            print("Already sent, skipping:", job["route"])
            continue

        if not is_relevant(job):
            print("Skip (cheap filter):", job["route"])
            continue

        if is_relevant_ai(job):
            send_notification(job)
            mark_as_sent(job["link"])
            print("Sent (AI approved):", job["route"])
        else:
            print("Skip (AI rejected):", job["route"])


while True:
    print("Checking subscribers...")
    check_new_subscribers()
    print("Checking jobs...")
    check_jobs()
    print("Sleeping for 15 minutes...")
    time.sleep(900)