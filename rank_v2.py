"""Deterministic commercial-role ranking for replacement scraper v2.

No network, no email, no writes to historical state. Inputs: v2_jobs.json.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
import config

ROOT = Path(__file__).parent
INCLUDE = [
    (r"strategic partnerships?|partnerships? (manager|lead|associate|specialist)|partner(ship)? (manager|lead|development|success|sales|account|ecosystem)", 46, "partnerships"),
    (r"business development|alliances?|channel (sales|manager|development|partnerships?)|ecosystem (manager|lead)", 43, "business development"),
    (r"category (manager|management|lead|strategy)|vendor (manager|management)|supplier (manager|management|partnerships?)|revenue growth|commercial (manager|lead|strategy)", 42, "category / commercial"),
    (r"(strategic|enterprise|key|national|global) account (manager|management|executive|lead)|account (manager|management)|customer development manager", 39, "enterprise accounts"),
    (r"sales manager|sales lead|customer success manager|marketplace (manager|lead)|go.to.market", 30, "commercial sales"),
]
BLOCK = [
    r"\bintern(ship)?\b|\bjunior\b|\bentry.level\b|\bgraduate trainee\b",
    r"\b(sdr|bdr)\b|sales development representative|business development representative",
    r"\binside sales\b|\bretail sales\b|\bdoor.to.door\b|\bfield sales representative\b",
    r"\b(engineer|developer|scientist|designer|recruiter|attorney|counsel|accountant)\b",
    r"\b(product manager|program manager|project manager)\b",
    r"\b(technical program manager|engineering manager|technical project manager|technical delivery manager)\b",
    r"\b(marketing|advertising|ad sales|media buying|procurement analyst)\b",
    r"\b(technology sourcing|strategic sourcing|procurement)\b",
    r"\b(coordinator|administrator)\b",
    r"\b(revenue accounting|technical accounting|financial reporting|controller|audit manager)\b",
]
# Conservative: unknown geography goes to review rather than falsely treated as US.
US_STATES = r"\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b"
US_WORDS = ("united states", "usa", "u.s.", "us remote", "remote - us", "remote (us)", "chicago", "new york", "san francisco", "los angeles", "dallas", "austin", "boston", "atlanta", "seattle", "houston", "denver", "washington, dc", "bay area", "california", "illinois", "texas")
NON_US = ("canada", "united kingdom", "london", "india", "pakistan", "germany", "france", "singapore", "australia", "netherlands", "ireland", "poland", "spain", "brazil", "mexico", "japan", "israel", "dubai", "uae")
PREFERRED = ("chicago", "new york", "nyc", "brooklyn", "san francisco", "bay area", "los angeles", "dallas", "austin", "palo alto", "san jose", "oakland")
TARGETS = tuple(x.split("|")[0].lower() for x in config.TARGET_COMPANIES)

def location_class(location):
    raw = location or ""
    s = raw.lower()
    us = any(x in s for x in US_WORDS) or bool(re.search(US_STATES, raw))
    foreign = any(x in s for x in NON_US) or bool(re.search(r"\\b(?:munich|berlin|hamburg|frankfurt|paris|toronto|vancouver)\\b",s))
    # Country prefixes such as DE - Munich are not US state abbreviations.
    if re.match(r"^\\s*(?:DE|FR|GB|UK|CA|IN|AU|NL|IE|SG)\\s*[-–|:]\\s*",raw,re.I) and not any(x in s for x in US_WORDS):
        return "non_us"
    if foreign and not any(x in s for x in US_WORDS):
        return "non_us"
    if us:
        return "us"  # Multi-location jobs may mention both US and non-US.
    if foreign:
        return "non_us"
    return "review"

def evaluate(job):
    title = (job.get("title") or "").strip()
    if not title:
        return None, "no_title"
    t = title.lower()
    if re.search(r"\b(technical account manager|technical customer success|technical partnerships? manager)\b",t) and not re.search(r"enterprise|commercial|revenue|sales|renewals?|expansion|partnerships?", (job.get("description") or "").lower()):
        return None, "technical_fit_unverified"
    if any(re.search(p, t, re.I) for p in BLOCK):
        return None, "blocked_title"
    matches = [(score, label) for p, score, label in INCLUDE if re.search(p, t, re.I)]
    if not matches:
        return None, "unrelated_title"
    level = location_class(job.get("location", ""))
    if level == "non_us":
        return None, "non_us"
    score, track = max(matches)
    if re.search(r"\b(assistant|associate)\s+(?:manager|account manager|partnerships? manager|category manager)",t):
        score += 3
    if re.search(r"\b(manager|management)\b",t):
        score += 6
    if re.search(r"\b(senior|sr\.?|principal|staff)\b", t):
        score += 8
    if re.search(r"\b(director|vice president|\bvp\b|chief|head of)\b", t):
        score -= 12
    if any(x in t for x in ("enterprise", "strategic", "key account", "global", "national")):
        score += 8
    if any(x in (job.get("company") or "").lower() for x in TARGETS):
        score += 7
    if level == "us":
        score += 10
    if any(x in (job.get("location") or "").lower() for x in PREFERRED):
        score += 7
    if level == "review":
        score -= 15
    result = dict(job)
    result.update(score=score, track=track, location_status=level, fit_reason=f"{track}; commercial title and level screened", cover_letter_decision="review_required_or_high_fit_optional")
    return result, "accepted"

def role_key(job):
    """Same company and normalized role, regardless of location or requisition."""
    company = re.sub(r"[^a-z0-9]+", " ", (job.get("company") or "").casefold()).strip()
    title = (job.get("title") or "").casefold()
    title = re.sub(r"\\b(sr\\.?|senior)\\b", "senior", title)
    title = re.sub(r"\\s*\\([^)]*(?:remote|hybrid|chicago|new york|san francisco|los angeles|dallas|usa|united states)[^)]*\\)", "", title)
    title = re.sub(r"\\s*[-–|]\\s*(?:remote|hybrid|chicago|new york|san francisco|los angeles|dallas|usa|united states)$", "", title)
    return company, re.sub(r"[^a-z0-9]+", " ", title).strip()

def shortlist(jobs, limit=40):
    counts = Counter()
    accepted = []
    ids = set()
    for job in jobs:
        identity = job.get("id") or job.get("url")
        if identity in ids:
            counts["duplicate"] += 1
            continue
        ids.add(identity)
        result, reason = evaluate(job)
        counts[reason] += 1
        if result:
            accepted.append(result)
    accepted.sort(key=lambda j: (-j["score"], j.get("company", ""), j.get("title", ""), j.get("id", "")))
    # Separate review-only geography rather than silently mailing ambiguous locations.
    eligible = [j for j in accepted if j["location_status"] == "us"]
    review = [j for j in accepted if j["location_status"] == "review"]
    # Keep the highest-scoring posting of equivalent roles across locations/IDs.
    seen_roles = set()
    unique_eligible = []
    for job in eligible:
        key = role_key(job)
        if key in seen_roles:
            counts["same_role_different_posting"] += 1
            continue
        seen_roles.add(key)
        unique_eligible.append(job)
    # Diversify alerts without discarding other distinct roles.
    company_counts = Counter()
    diversified = []
    for job in unique_eligible:
        company = (job.get("company") or "").strip().casefold()
        if company_counts[company] >= 2:
            continue
        diversified.append(job)
        company_counts[company] += 1
        if len(diversified) >= limit:
            break
    return {"top": diversified, "review_location": review[:limit],
            "counts": dict(counts), "total_us_matches": len(unique_eligible),
            "total_location_review": len(review)}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="v2_jobs.json")
    p.add_argument("--output", default="v2_shortlist.json")
    p.add_argument("--limit", type=int, default=40)
    a = p.parse_args()
    payload = json.loads((ROOT / a.input).read_text(encoding="utf-8"))
    result = shortlist(payload["jobs"], limit=a.limit)
    result["companies_checked"] = payload.get("companies_checked")
    result["raw_jobs"] = len(payload["jobs"])
    (ROOT / a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Raw:", result["raw_jobs"], "US matches:", result["total_us_matches"],
          "Review location:", result["total_location_review"], "Shortlist:", len(result["top"]))
    for j in result["top"][:15]:
        print(j["score"], j["company"], "|", j["title"], "|", j["location"])
if __name__ == "__main__":
    main()
