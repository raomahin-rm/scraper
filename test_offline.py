"""Offline test with fake jobs. No network needed."""
from datetime import datetime, timedelta, timezone
import job_scraper as js

now = datetime.now(timezone.utc)

def J(uid, company, title, loc, hrs, desc, src="adzuna"):
    return js.Job(src, uid, company, title, loc, f"https://x.com/{uid}", now - timedelta(hours=hrs), desc)

jobs = [
    J("1", "Lyft", "Senior Partnerships Manager, Marketplace", "New York, NY", 5,
      "Own B2B partnerships and channel strategy for our marketplace. P&L, negotiation, forecasting. 6+ years experience.", "greenhouse"),
    J("2", "Acme", "Director of Business Development", "Chicago, IL", 5, "Lead BD."),
    J("3", "Block", "Mid-Market Business Development Rep - AfterPay", "New York, NY", 5, "BD rep."),
    J("4", "Brex", "Category Manager, Supplier Programs", "Remote - US", 10,
      "Category management, supplier negotiation, pricing, SaaS, enterprise accounts. 8 years.", "greenhouse"),
    J("5", "OldCo", "Partnerships Manager", "Chicago", 200, "Old posting."),
    J("6", "Samsara", "Senior Partner Account Executive, UK - Insurance", "London - UK2", 3, "Partners.", "greenhouse"),
    J("7", "OpenAI", "Strategic Finance Partner, GPT Infra", "San Francisco Remote", 3, "Finance.", "ashby"),
    J("8", "Procter & Gamble", "Key Account Manager, Customer Development", "Atlanta, GA", 3,
      "Key account management, retail, negotiation, P&L, forecasting, category. 7 years.", "adzuna"),
    J("9", "NoSponsor Inc", "Partnerships Manager", "Boston, MA", 3,
      "Great role. We are unable to provide visa sponsorship for this position.", "adzuna"),
    J("10", "Sponsorly", "Partnerships Manager", "Austin, TX", 3,
      "Great role. Visa sponsorship is available for the right candidate. Partnerships, channel, SaaS, b2b.", "adzuna"),
    J("11", "OpenAI", "B2B Ecosystem Lead, Business Development", "San Francisco Remote", 2,
      "Partnerships with enterprise. LLM and generative AI. Foundation models. machine learning.", "ashby"),
    J("12", "Instacart", "Partnerships Manager", "US-Remote; US-Chicago; CA-Toronto", 4, "Partnerships.", "greenhouse"),
    J("13", "Oldapplied Co", "Partnerships Manager", "Denver, CO", 4, "Partnerships channel b2b saas enterprise.", "adzuna"),
    J("14", "Uber", "Account Executive, Enterprise", "Toronto, ON", 4, "Enterprise.", "adzuna"),
    J("15", "Lyft", "Enterprise Account Manager", "New York, NY", 100,
      "Enterprise account management, B2B, partnerships, negotiation.", "greenhouse"),
    J("16", "Lyft", "Enterprise Account Manager", "San Francisco, CA", 100,
      "Enterprise account management, B2B, partnerships, negotiation.", "greenhouse"),
    J("17", "Acme", "Key Account Manager", "Gurugram, Haryana", 5, "Key accounts.", "adzuna"),
    J("18", "Acme", "Key Account Manager", "Shenzhen, Guangdong", 5, "Key accounts.", "adzuna"),
]
# Tests for pieces
assert js.location_info("Chicago, IL")[0] == "tier1"
assert js.location_info("US-Remote; CA-Toronto")[0] == "us"
assert js.location_info("London - UK2")[0] == "non_us"
assert js.location_info("Toronto, ON")[0] == "non_us"
assert js.location_info("Denver, CO - Hybrid")[0] == "us"
assert js.location_info("Remote")[0] == "remote"
assert js.sponsor_signal("We will not sponsor visas") == "no"
assert js.sponsor_signal("Unable to provide visa sponsorship") == "no"
assert js.sponsor_signal("Candidates must not require sponsorship") == "no"
assert js.sponsor_signal("Visa sponsorship is available") == "yes"
assert js.sponsor_signal("We do sponsor H-1B") == "yes"
assert js.sponsor_signal("Great team and benefits") == ""

applied = (set(), {"Oldapplied Co": (now - timedelta(days=10)).date(), "Block": None})
sponsors = js.load_sponsors()
top, rejected, stats = js.run(jobs, [], {}, applied, sponsors)
for j in top:
    print(round(j.final), "|", j.title, "|", j.company, "|", j.resume, "|", j.visa or "-", "|", " ".join(j.tags), "|", j.flags)
print(stats)
titles = [j.title for j in top]
assert not any("Rep" in t for t in titles)
assert not any("Strategic Finance" in t for t in titles)
assert stats["non_us"] == 4 and stats["no_sponsor"] == 1
assert any(j.company == "Sponsorly" and j.visa == "yes" for j in top)
assert any(j.company == "OpenAI" and j.resume == "AI/Tech resume" for j in top)
assert any(j.company == "Procter & Gamble" and j.resume == "Commercial resume" for j in top)
assert any(j.company == "Oldapplied Co" and "applied here" in j.flags for j in top) or stats["low"] > 0
body, text = js.build_email(top, stats, ["greenhouse/foo: 404 Not Found"])
assert "foo" in body
js.build_csv(top)
assert sum(1 for j in top if j.company == "Lyft") == 3
js.print_debug(jobs, top)
print("OK")
