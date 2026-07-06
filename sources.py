import requests

# Common adapter interface: fetch_<ats>_jobs(slug) -> list of dicts shaped
# {title, company, location, link, id}. Add a new provider by writing one
# more function with this signature; callers dispatch by the company's
# stored `ats` value (see bot.get_company_ats / main.check_jobs).


def fetch_greenhouse_jobs(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    response = requests.get(url, timeout=10)
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


def fetch_lever_jobs(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    response = requests.get(url, timeout=10)
    data = response.json()

    jobs = []
    for job in data:
        jobs.append({
            "title": job["text"],
            "company": slug,
            "location": job["categories"]["location"],
            "link": job["hostedUrl"],
            "id": job["id"],
        })

    return jobs


WORKDAY_PAGE_SIZE = 20
WORKDAY_MAX_JOBS = 200


def fetch_workday_jobs(company):
    # Workday has no public API; this is the internal CXS endpoint career
    # sites call themselves. It's unofficial and may change without notice,
    # so every response is treated as untrusted: malformed pages or fields
    # are logged and skipped rather than allowed to raise.
    tenant = company["tenant"]
    site = company["site"]
    host = company["host"]

    api_url = f"https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    careers_url = f"https://{tenant}.{host}.myworkdayjobs.com/{site}"

    jobs = []
    offset = 0

    while len(jobs) < WORKDAY_MAX_JOBS:
        try:
            response = requests.post(
                api_url,
                json={"appliedFacets": {}, "limit": WORKDAY_PAGE_SIZE, "offset": offset, "searchText": ""},
                headers={"Accept": "application/json"},
                timeout=10,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            print(f"Workday API error for {tenant}/{site}:", e)
            break

        if not isinstance(data, dict):
            print(f"Workday: unexpected response shape for {tenant}/{site}, stopping")
            break

        postings = data.get("jobPostings")
        if not postings:
            break

        for posting in postings:
            try:
                title = posting["title"]
                external_path = posting["externalPath"]
            except (KeyError, TypeError) as e:
                print(f"Workday: skipping malformed posting for {tenant}/{site}:", e)
                continue

            jobs.append({
                "title": title,
                "company": tenant,
                "location": posting.get("locationsText", ""),
                "link": careers_url + external_path,
                "id": external_path,
            })

            if len(jobs) >= WORKDAY_MAX_JOBS:
                break

        total = data.get("total")
        offset += WORKDAY_PAGE_SIZE
        if total is not None and offset >= total:
            break
        if len(postings) < WORKDAY_PAGE_SIZE:
            # Short page: no more results even if `total` was missing or wrong.
            break

    return jobs
