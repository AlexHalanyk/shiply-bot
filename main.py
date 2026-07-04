from bot import (
    send_notification,
    is_relevant_ai,
    is_relevant_ai_ollama,
    already_sent,
    mark_as_sent,
    check_incoming_messages,
    get_companies,
    LLM_BACKEND,
)
from sources import fetch_greenhouse_jobs
import time

KEYWORDS = ["graduate", "junior", "intern", "engineer", "software"]


def is_relevant(job):
    title = job["title"].lower()
    return any(keyword in title for keyword in KEYWORDS)


def check_jobs():
    check_relevance = is_relevant_ai_ollama if LLM_BACKEND == "ollama" else is_relevant_ai

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

        if LLM_BACKEND == "cascade":
            # Gemma is free/local, so it takes the first (bulk-rejecting)
            # pass; only jobs it approves cost a Gemini call.
            gemma_decision = is_relevant_ai_ollama(job)
            if gemma_decision is None:
                print("Skip (AI error, will retry):", job["title"])
                continue

            if not gemma_decision:
                mark_as_sent(job["link"])
                print("Skip (AI rejected (gemma)):", job["title"])
                continue

            gemini_decision = is_relevant_ai(job)
            if gemini_decision is None:
                print("Skip (AI error, will retry):", job["title"])
                continue

            mark_as_sent(job["link"])
            if gemini_decision:
                send_notification(job)
                print("Sent (cascade approved):", job["title"])
            else:
                print("Skip (AI rejected (gemini after gemma pass)):", job["title"])
            continue

        ai_decision = check_relevance(job)
        if ai_decision is None:
            # Don't mark_as_sent here: the LLM call failed (e.g. rate limit),
            # not the job — retry it next cycle once quota recovers.
            print("Skip (AI error, will retry):", job["title"])
            continue

        if ai_decision:
            send_notification(job)
            mark_as_sent(job["link"])
            print("Sent (AI approved):", job["title"])
        else:
            # Marked sent even though rejected, so a rejected job isn't
            # re-sent to the LLM (and re-rejected) every cycle.
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