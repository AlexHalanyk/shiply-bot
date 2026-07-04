from bot import send_notification, is_relevant_ai, already_sent, mark_as_sent, check_incoming_messages, get_companies
from sources import fetch_greenhouse_jobs
import time

KEYWORDS = ["graduate", "junior", "intern", "engineer", "software"]


def is_relevant(job):
    title = job["title"].lower()
    return any(keyword in title for keyword in KEYWORDS)


def check_jobs():
    jobs = []
    for slug in get_companies():
        jobs += fetch_greenhouse_jobs(slug)

    for job in jobs:
        if already_sent(job["link"]):
            print("Already sent, skipping:", job["title"])
            continue

        if not is_relevant(job):
            print("Skip (cheap filter):", job["title"])
            continue

        if is_relevant_ai(job):
            send_notification(job)
            mark_as_sent(job["link"])
            print("Sent (AI approved):", job["title"])
        else:
            mark_as_sent(job["link"])
            print("Skip (AI rejected):", job["title"])


if __name__ == "__main__":
    while True:
        print("Checking messages...")
        check_incoming_messages()
        print("Checking jobs...")
        check_jobs()
        print("Sleeping for 15 minutes...")
        time.sleep(900)