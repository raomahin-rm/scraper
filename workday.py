"""Workday job boards, read through Workday's public JSON feed (no login).

The method: send a search to
    https://{tenant}.{sub}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
then open each interesting posting's detail address for its real posted date,
all of its locations and the full description.

Each company needs three codes: tenant, board and subdomain. They are in the
address of any job on the company's Workday careers page, for example
    https://target.wd5.myworkdayjobs.com/en-US/targetcareers/job/...
        tenant = target   subdomain = wd5   board = targetcareers
If the board or subdomain is missing, or the saved ones stop working, this
module tries to find them itself from the tenant name.

Written for this project from Workday's public behavior.
"""
import html
import re
import time
from datetime import date, timedelta
from urllib.parse import urlparse

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
SUBDOMAINS = ["wd5", "wd1", "wd3", "wd12", "wd103", "wd501", "wd2", "wd10",
              "wd108", "wd502", "wd503"]
LIMIT = 20          # results per page (Workday's maximum is 20)
MAX_OFFSET = 200    # stop paging after this many results per search word
DETAIL_CAP = 60     # most postings opened in detail per company per run
PAUSE = 0.25        # seconds between requests, to be polite

LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
MULTI_LOC_RE = re.compile(r"^\s*\d+\s+locations?\s*$", re.I)

_session = requests.Session()
_session.headers.update(HEADERS)


def _request(method, url, tries=3, timeout=25, **kw):
    last = None
    for i in range(tries):
        try:
            r = _session.request(method, url, timeout=timeout, **kw)
        except requests.RequestException as e:
            last = str(e)
            time.sleep(1.5 * (i + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            last = f"HTTP {r.status_code}"
            time.sleep(1.5 * (i + 1))
            continue
        return r
    raise RuntimeError(f"{method} failed after {tries} tries: {last}")


def _clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _tail(path):
    # /job/Houston-TX/Account-Manager_R-100380  ->  Account-Manager_R-100380
    return path.rstrip("/").split("/")[-1]


def _req_id(path):
    tail = _tail(path)
    m = re.search(r"_([A-Za-z0-9][A-Za-z0-9-]*)$", tail)
    return m.group(1) if m else tail


def _path_location(path):
    # /job/Chicago-IL/Title_R1 -> "Chicago IL" (only used if the list gives none)
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "job" and parts[-2].lower() != "job":
        return parts[-2].replace("-", " ")
    return ""


def _from_postedon(s):
    """'Posted 12 Days Ago' -> a date about 12 days back. '30+' counts as 30."""
    if not s:
        return None
    s = s.lower()
    if "today" in s:
        days = 0
    elif "yesterday" in s:
        days = 1
    else:
        m = re.search(r"(\d+)\+?\s*day", s)
        if not m:
            return None
        days = int(m.group(1))
    return (date.today() - timedelta(days=days)).isoformat()


def _detail(base_url, tenant, board, path):
    """One posting's detail data, or {} if it cannot be read."""
    try:
        r = _request("GET", f"{base_url}/wday/cxs/{tenant}/{board}{path}", timeout=15)
        if r.ok:
            return r.json().get("jobPostingInfo", {}) or {}
    except Exception:
        pass
    return {}


def _detail_locations(detail):
    places, seen = [], set()
    for p in [detail.get("location") or "", *(detail.get("additionalLocations") or [])]:
        p = (p or "").strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            places.append(p)
    return "; ".join(places)


_discover_spent = [0.0]
DISCOVER_BUDGET_S = 480  # total seconds per run allowed for guessing boards


def discover(tenant):
    """Find (subdomain, board) for a tenant by visiting its front page."""
    started = time.time()
    try:
        return _discover(tenant)
    finally:
        _discover_spent[0] += time.time() - started


def _discover(tenant):
    if _discover_spent[0] > DISCOVER_BUDGET_S:
        return None
    for sub in SUBDOMAINS:
        host = f"{tenant}.{sub}.myworkdayjobs.com"
        try:
            r = _session.get(f"https://{host}/", timeout=6, allow_redirects=True)
        except requests.RequestException:
            continue
        final = urlparse(r.url)
        if r.status_code >= 400 or host not in final.netloc.lower():
            continue
        parts = [p for p in final.path.split("/") if p]
        if parts and LOCALE_RE.match(parts[0]):
            parts = parts[1:]
        if parts and parts[0].lower() not in ("login", "job", "jobs", "wday", "sso"):
            return sub, parts[0]
    return None


def _search(base_url, tenant, board, term, offset):
    return _request(
        "POST", f"{base_url}/wday/cxs/{tenant}/{board}/jobs",
        json={"appliedFacets": {}, "limit": LIMIT, "offset": offset, "searchText": term},
        headers={"Content-Type": "application/json"},
    )


def fetch(c, terms, title_ok):
    """Read one company. c needs tenant and, ideally, board and subdomain.

    title_ok(title) decides which postings are worth opening in detail.
    Returns (rows, note). Each row is a dict: title, url, location, posted,
    req, description. Raises RuntimeError if the board cannot be read at all.
    """
    tenant = c["tenant"]
    board = c.get("board") or ""
    sub = c.get("subdomain") or ""
    notes = []

    ok = False
    if board and sub:
        probe = _search(f"https://{tenant}.{sub}.myworkdayjobs.com", tenant, board, terms[0], 0)
        ok = probe.ok
    if not ok:
        found = discover(tenant)
        if not found:
            raise RuntimeError("could not find this company's Workday board "
                               "(the tenant name is probably wrong)")
        sub, board = found
        notes.append(f"auto-found {sub}/{board}")
    base_url = f"https://{tenant}.{sub}.myworkdayjobs.com"

    seen_paths, cands, bad = set(), [], None
    for term in terms:
        offset = 0
        while offset <= MAX_OFFSET:
            r = _search(base_url, tenant, board, term, offset)
            if not r.ok:
                bad = r.status_code
                break
            body = r.json()
            posts = body.get("jobPostings") or []
            if not posts:
                break
            for j in posts:
                path = j.get("externalPath") or ""
                if not path or path in seen_paths:
                    continue
                seen_paths.add(path)
                if title_ok(j.get("title", "")):
                    cands.append(j)
            offset += LIMIT
            if offset >= (body.get("total") or 0):
                break
            time.sleep(PAUSE)
    if bad and not seen_paths:
        raise RuntimeError(f"HTTP {bad}")

    rows = []
    for n, j in enumerate(cands):
        path = j["externalPath"]
        detail = _detail(base_url, tenant, board, path) if n < DETAIL_CAP else {}
        loc = j.get("locationsText") or _path_location(path)
        if MULTI_LOC_RE.match(loc or ""):
            loc = _detail_locations(detail) or loc
        rows.append({
            "title": j.get("title", ""),
            "url": f"{base_url}/en-US/{board}/job/{_tail(path)}",
            "location": loc,
            "posted": detail.get("startDate") or _from_postedon(j.get("postedOn")),
            "req": _req_id(path),
            "description": _clean(detail.get("jobDescription")),
        })
        time.sleep(PAUSE / 2)

    notes.append(f"{len(rows)} matched / {len(seen_paths)} scanned")
    return rows, "; ".join(notes)
