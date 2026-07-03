import requests


def fetch_greenhouse_jobs(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    response = requests.get(url)
    data = response.json()

    jobs = []
    for job in data["jobs"]:
        jobs.append({
            "title": job["title"],
            "company": job["company_name"],
            "location": job["location"]["name"],
            "link": job["absolute_url"],
            "id": job["id"],
        })

    return jobs
