"""Offline test with fake jobs. No network needed."""
from datetime import datetime, timedelta, timezone
import job_scraper as js

now = datetime.now(timezone.utc)
def J(uid, company, title, loc, hrs, desc, src="greenhouse"):
    return js.Job(src, uid, company, title, loc, f"https://x.com/{uid}", now - timedelta(hours=hrs), desc)

jobs = [
    J("1", "Lyft", "Senior Partnerships Manager, Marketplace", "New York, NY", 5,
      "Own B2B partnerships and channel strategy for our marketplace. P&L, negotiation, forecasting. 6+ years experience."),
    J("2", "Acme", "Director of Business Development", "Chicago, IL", 5, "Lead BD."),
    J("3", "Acme", "Territory Sales Representative", "Chicago, IL", 5, "Field sales territory."),
    J("4", "Brex", "Category Manager, Supplier Programs", "Remote - US", 10,
      "Category management, supplier negotiation, pricing, SaaS, enterprise accounts. 8 years."),
    J("5", "OldCo", "Partnerships Manager", "Chicago", 200, "Old posting. Partnerships."),
    J("6", "PolicyOrg", "Senior Policy Manager", "Washington, DC", 12, "Regulatory policy for fintech and payments. 7 years.", "adzuna"),
    J("7", "Acme", "Partner Engineer", "Chicago", 3, "Engineer."),
    J("8", "Acme", "Strategic Account Manager", "Chicago, IL", 3, "Strategic account management, enterprise, negotiation, P&L, b2b, forecast. 10 years.", "adzuna"),
    J("9", "Gusto", "Partnerships Manager", "London, UK", 3, "Partnerships.", "greenhouse"),
]
top, reviewed, stats = js.run(jobs, [], {}, {("brex", "categorymanagersupplierprograms")})
for j in top:
    print(round(j.final), j.track, j.resume, "|", j.title, "|", j.company, "|", j.flags)
print(stats)
body, text = js.build_email(top, stats, ["greenhouse/foo: 404 Not Found"])
assert "Lyft" in body and "foo" in body
js.build_csv(top)
print("OK")
