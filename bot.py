import datetime
import os
import re
import time
import requests
from dotenv import load_dotenv
from google import genai
import sqlite3

load_dotenv()
token = os.getenv("TELEGRAM_TOKEN")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")
OLLAMA_URL = os.getenv("OLLAMA_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:12b")

DEFAULT_PROFILE = "graduate or junior software engineering roles in the UK"

DB_PATH = os.getenv("JOBRADAR_DB_PATH", "data/sent_jobs.db")
db = sqlite3.connect(DB_PATH)
db_cursor = db.cursor()

db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS sent_jobs (
        link TEXT PRIMARY KEY
    )
""")


def _migrate_sent_jobs_schema(cursor, conn):
    # Additive-only migration: existing rows keep decision/processed_at as
    # NULL rather than losing data via a drop-and-recreate.
    cursor.execute("PRAGMA table_info(sent_jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "decision" not in existing_columns:
        cursor.execute("ALTER TABLE sent_jobs ADD COLUMN decision TEXT")
        existing_columns.add("decision")
    if "processed_at" not in existing_columns:
        cursor.execute("ALTER TABLE sent_jobs ADD COLUMN processed_at TEXT")
        existing_columns.add("processed_at")

    if "profile" not in existing_columns:
        # A job is now evaluated once per distinct subscriber profile, so
        # link alone can no longer be the primary key. SQLite can't alter a
        # PRIMARY KEY in place, so rebuild the table under (link, profile)
        # and backfill existing rows under the old single global profile.
        cursor.execute("ALTER TABLE sent_jobs RENAME TO sent_jobs_old")
        cursor.execute("""
            CREATE TABLE sent_jobs (
                link TEXT NOT NULL,
                profile TEXT NOT NULL,
                decision TEXT,
                processed_at TEXT,
                PRIMARY KEY (link, profile)
            )
        """)
        cursor.execute(
            """
            INSERT INTO sent_jobs (link, profile, decision, processed_at)
            SELECT link, ?, decision, processed_at FROM sent_jobs_old
            """,
            (DEFAULT_PROFILE,),
        )
        cursor.execute("DROP TABLE sent_jobs_old")

    conn.commit()


_migrate_sent_jobs_schema(db_cursor, db)

db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscribers (
        chat_id INTEGER PRIMARY KEY
    )
""")


def _migrate_subscribers_schema(cursor, conn):
    # Additive-only migration: existing subscribers keep their chat_id and
    # get backfilled onto the default profile rather than losing data.
    cursor.execute("PRAGMA table_info(subscribers)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "profile" not in existing_columns:
        cursor.execute("ALTER TABLE subscribers ADD COLUMN profile TEXT")
    if "first_name" not in existing_columns:
        cursor.execute("ALTER TABLE subscribers ADD COLUMN first_name TEXT")
    conn.commit()

    cursor.execute("UPDATE subscribers SET profile = ? WHERE profile IS NULL", (DEFAULT_PROFILE,))
    conn.commit()


_migrate_subscribers_schema(db_cursor, db)

db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        slug TEXT PRIMARY KEY
    )
""")


def _migrate_companies_schema(cursor, conn):
    # Additive-only migration: existing rows get the default ATS via the
    # column's own DEFAULT, so no separate backfill pass is needed.
    cursor.execute("PRAGMA table_info(companies)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "ats" not in existing_columns:
        cursor.execute("ALTER TABLE companies ADD COLUMN ats TEXT NOT NULL DEFAULT 'greenhouse'")
        existing_columns.add("ats")
    # tenant/site/host are only populated for Workday companies; NULL for
    # everything else, so no default/backfill value makes sense here.
    if "tenant" not in existing_columns:
        cursor.execute("ALTER TABLE companies ADD COLUMN tenant TEXT")
        existing_columns.add("tenant")
    if "site" not in existing_columns:
        cursor.execute("ALTER TABLE companies ADD COLUMN site TEXT")
        existing_columns.add("site")
    if "host" not in existing_columns:
        cursor.execute("ALTER TABLE companies ADD COLUMN host TEXT")
        existing_columns.add("host")
    conn.commit()


_migrate_companies_schema(db_cursor, db)

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


LEVER_URL_RE = re.compile(r"jobs\.lever\.co/([a-zA-Z0-9-]+)")


def extract_lever_slug(text):
    # Only matches explicit jobs.lever.co URLs (not bare slugs, which stay
    # ambiguous and go through the Greenhouse-then-Lever probe fallback
    # below). Trailing path segments (e.g. a specific posting id) are
    # ignored -- only the org slug right after the host is captured.
    match = LEVER_URL_RE.search(text)
    if match:
        return match.group(1)
    return None


# "workday:{tenant}:{site}" has no way to express the host, since wd1 is by
# far the most common; a full careers URL (which encodes the real host) is
# the fallback for tenants on wd3/wd5.
WORKDAY_DEFAULT_HOST = "wd1"
WORKDAY_SHORTHAND_RE = re.compile(r"^workday:([a-zA-Z0-9-]+):([a-zA-Z0-9_-]+)$")
WORKDAY_URL_RE = re.compile(
    r"https?://(?P<tenant>[a-zA-Z0-9-]+)\.(?P<host>wd\d+)\.myworkdayjobs\.com/(?P<path>[^\s?#]+)"
)
_WORKDAY_LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def _parse_workday_url(text):
    match = WORKDAY_URL_RE.search(text)
    if not match:
        return None

    segments = [segment for segment in match.group("path").split("/") if segment]
    if not segments:
        return None

    # Some tenants prefix the site with a locale segment (e.g. "en-US/External").
    if len(segments) > 1 and _WORKDAY_LOCALE_SEGMENT_RE.match(segments[0]):
        site = segments[1]
    else:
        site = segments[0]

    return {"tenant": match.group("tenant"), "host": match.group("host"), "site": site}


def _parse_workday_shorthand(text):
    match = WORKDAY_SHORTHAND_RE.match(text)
    if not match:
        return None
    tenant, site = match.groups()
    return {"tenant": tenant, "host": WORKDAY_DEFAULT_HOST, "site": site}


def extract_workday_company(text):
    return _parse_workday_url(text) or _parse_workday_shorthand(text)


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})


def send_notification(job, chat_ids):
    text = f"💼  New Job\n{job['title']} at {job['company']}\n{job['location']}\n{job['link']}"
    for subscriber_id in chat_ids:
        send_message(subscriber_id, text)

def _build_relevance_prompt(job, profile=DEFAULT_PROFILE):
    return f"""You are helping a UK job seeker find relevant vacancies.

Job details:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}

The job seeker is looking for: {profile}

Does this job match what the job seeker is looking for?

Apprenticeships, placements and early-careers programmes count as YES.

Data, analytics, platform, and ML-ops roles count as NO, unless the title
itself contains one of: graduate, junior, intern, apprentice, early careers.

Answer with only one word: YES or NO."""


def is_relevant_ai(job, profile=DEFAULT_PROFILE):
    prompt = _build_relevance_prompt(job, profile)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
    except Exception as e:
        # None (not False) signals "couldn't get a decision" so the caller
        # retries this job next cycle instead of treating it as rejected.
        print("Gemini API error:", e)
        return None
    finally:
        # Free tier caps Gemini at 5 requests/minute; this keeps every call
        # (success or failure) under that limit.
        time.sleep(13)

    # The model doesn't always answer with a bare "YES"/"NO" (e.g. "Yes.",
    # a full sentence), so normalise and check for containment, not equality.
    decision = response.text.strip().upper()
    return "YES" in decision


def is_relevant_ai_ollama(job, profile=DEFAULT_PROFILE):
    prompt = _build_relevance_prompt(job, profile)

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"num_predict": 5},
            },
            timeout=300,  # CPU inference is slow
        )
        text = response.json().get("response")
        if not text:
            raise ValueError("empty or missing 'response' field")
        decision = text.strip().upper()
    except Exception as e:
        # Same contract as is_relevant_ai: None means "couldn't get a
        # decision", so the caller retries the job next cycle.
        print("Ollama API error:", e)
        return None

    return "YES" in decision

def already_sent(link, profile=DEFAULT_PROFILE):
    db_cursor.execute("SELECT link FROM sent_jobs WHERE link = ? AND profile = ?", (link, profile))
    return db_cursor.fetchone() is not None


def mark_as_sent(link, decision, profile=DEFAULT_PROFILE):
    db_cursor.execute(
        "INSERT OR IGNORE INTO sent_jobs (link, profile, decision, processed_at) VALUES (?, ?, ?, ?)",
        (link, profile, decision, datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    db.commit()

def add_subscriber(chat_id, first_name=None):
    # Only first_name is overwritten on conflict: /start must never reset a
    # profile the subscriber already customised via /profile.
    db_cursor.execute(
        """
        INSERT INTO subscribers (chat_id, profile, first_name) VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET first_name = excluded.first_name
        """,
        (chat_id, DEFAULT_PROFILE, first_name),
    )
    db.commit()


def get_subscribers():
    db_cursor.execute("SELECT chat_id FROM subscribers")
    rows = db_cursor.fetchall()
    return [row[0] for row in rows]


def get_profile(chat_id):
    db_cursor.execute("SELECT profile FROM subscribers WHERE chat_id = ?", (chat_id,))
    row = db_cursor.fetchone()
    return row[0] if row and row[0] else DEFAULT_PROFILE


def set_profile(chat_id, profile_text):
    db_cursor.execute(
        """
        INSERT INTO subscribers (chat_id, profile) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET profile = excluded.profile
        """,
        (chat_id, profile_text),
    )
    db.commit()


def get_distinct_profiles():
    db_cursor.execute("SELECT DISTINCT profile FROM subscribers WHERE profile IS NOT NULL")
    return [row[0] for row in db_cursor.fetchall()]


def get_subscribers_for_profile(profile):
    db_cursor.execute("SELECT chat_id FROM subscribers WHERE profile = ?", (profile,))
    return [row[0] for row in db_cursor.fetchall()]


def add_company(slug, ats="greenhouse", tenant=None, site=None, host=None):
    db_cursor.execute(
        "INSERT OR IGNORE INTO companies (slug, ats, tenant, site, host) VALUES (?, ?, ?, ?, ?)",
        (slug, ats, tenant, site, host),
    )
    db.commit()


def get_companies():
    db_cursor.execute("SELECT slug FROM companies")
    return [row[0] for row in db_cursor.fetchall()]


def get_company_ats(slug):
    db_cursor.execute("SELECT ats FROM companies WHERE slug = ?", (slug,))
    row = db_cursor.fetchone()
    return row[0] if row and row[0] else "greenhouse"


def get_company_workday_info(slug):
    db_cursor.execute("SELECT tenant, site, host FROM companies WHERE slug = ?", (slug,))
    row = db_cursor.fetchone()
    if row is None or None in row:
        return None
    tenant, site, host = row
    return {"tenant": tenant, "site": site, "host": host}


def is_valid_greenhouse_board(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        return False
    return response.status_code == 200


def is_valid_lever_board(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        return False
    return response.status_code == 200


def is_valid_workday_board(tenant, site, host):
    url = f"https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        response = requests.post(
            url,
            json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
            headers={"Accept": "application/json"},
            timeout=10,
        )
    except requests.RequestException:
        return False
    return response.status_code == 200


def _format_uptime(seconds):
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {secs}s"


def build_stats_reply(start_time):
    db_cursor.execute("SELECT COUNT(*) FROM sent_jobs")
    total = db_cursor.fetchone()[0]

    db_cursor.execute("SELECT decision, COUNT(*) FROM sent_jobs GROUP BY decision")
    breakdown = db_cursor.fetchall()

    lines = ["📊 Stats", f"Total jobs processed: {total}"]
    for decision, count in breakdown:
        label = decision or "unrecorded (pre-stats)"
        pct = (count / total * 100) if total else 0
        lines.append(f"  {label}: {count} ({pct:.1f}%)")

    lines.append(f"Tracked companies: {len(get_companies())}")
    lines.append(f"Subscribers: {len(get_subscribers())}")
    lines.append(f"Uptime: {_format_uptime(time.time() - start_time)}")

    return "\n".join(lines)


def _handle_update(update, start_time):
    message = update.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()

    if chat_id is None:
        return

    if text == "/start":
        add_subscriber(chat_id, chat.get("first_name"))
        print("New subscriber:", chat_id)
    elif text == "/stats":
        # Reply directly to the requester only — never a broadcast.
        send_message(chat_id, build_stats_reply(start_time))
    elif text == "/profile" or text.startswith("/profile "):
        profile_text = text[len("/profile"):].strip()
        if profile_text:
            set_profile(chat_id, profile_text)
            send_message(chat_id, f"✅ Profile saved:\n{profile_text}")
        else:
            send_message(chat_id, f"Current profile:\n{get_profile(chat_id)}")
    else:
        # Workday inputs ("workday:tenant:site" or a myworkdayjobs.com
        # URL) have a distinct shape that never overlaps with a bare
        # Greenhouse/Lever slug, so check for one first.
        workday_company = extract_workday_company(text)
        if workday_company is not None:
            tenant = workday_company["tenant"]
            site = workday_company["site"]
            host = workday_company["host"]
            if is_valid_workday_board(tenant, site, host):
                company_slug = f"{tenant}:{site}"
                add_company(company_slug, "workday", tenant=tenant, site=site, host=host)
                send_message(chat_id, f"✅ {company_slug} added, now tracking (Workday)")
                print("New company tracked:", company_slug, "(workday)")
            else:
                send_message(chat_id, f"❌ Workday board not found: {tenant}/{site}")
            return

        # An explicit jobs.lever.co URL already tells us the ATS, so treat
        # it as unambiguous too, same as an explicit Greenhouse URL below.
        lever_slug = extract_lever_slug(text)
        if lever_slug is not None:
            if is_valid_lever_board(lever_slug):
                add_company(lever_slug, "lever")
                send_message(chat_id, f"✅ {lever_slug} added, now tracking (Lever)")
                print("New company tracked:", lever_slug, "(lever)")
            else:
                send_message(chat_id, f"❌ Board not found: {lever_slug}")
            return

        slug = extract_greenhouse_slug(text)
        if slug is not None:
            # An explicit Greenhouse URL already tells us the ATS,
            # so there's no ambiguity to resolve — don't probe
            # Lever too.
            is_greenhouse_url = GREENHOUSE_SLUG_RE.search(text) is not None

            if is_valid_greenhouse_board(slug):
                add_company(slug, "greenhouse")
                send_message(chat_id, f"✅ {slug} added, now tracking (Greenhouse)")
                print("New company tracked:", slug, "(greenhouse)")
            elif not is_greenhouse_url and is_valid_lever_board(slug):
                add_company(slug, "lever")
                send_message(chat_id, f"✅ {slug} added, now tracking (Lever)")
                print("New company tracked:", slug, "(lever)")
            else:
                send_message(chat_id, f"❌ Board not found: {slug}")
        else:
            # Nothing recognised this input at all — still reply, so the
            # sender never sees silence and mistakes the bot for dead.
            send_message(chat_id, f"❌ Board not found: {text}")


def check_incoming_messages(start_time):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url)
    data = response.json()

    last_update_id = 0
    for update in data["result"]:
        try:
            _handle_update(update, start_time)
        except Exception as e:
            # One malformed/unexpected update must never kill the poll loop —
            # log and move on so every other chat (and /stats) keeps working.
            print(f"Error handling update {update.get('update_id')}:", e)

        last_update_id = update["update_id"]

    if last_update_id != 0:
        # Telegram keeps returning already-seen updates until they're
        # acknowledged; offset+1 marks everything up to here as read.
        requests.get(url, params={"offset": last_update_id + 1})