# Job Search V3 — Employer-Verified Discovery

**Current status:** V3 is implemented on `phase1-scraper-development`; the existing v2 daily mailer remains separate until v3 quality checks and live acceptance succeed. The v3 workflows are deliberately non-submitting and non-emailing during acceptance testing.

Inspired by [Heidi Miller's Daily Job Search](https://github.com/heidimillerpresents-png/claude-skills/tree/main/daily-job-search) (MIT licensed). The public cross-company feed is [Riley Dorrington's job-board-data](https://github.com/Riley-Dorrington/job-board-data) (the feed is external and its coverage, accuracy and availability are not guaranteed). Code here is independently implemented around the source's discovery/verification approach.

## Principles

1. **Broader discovery:** Search a multi-ATS feed rather than relying only on the 305 manually configured company entries. The feed may cover many more companies; it does not mean 1.4M opportunities fit the candidate.
2. **Discovery date is not publication date:** `first_seen` gates the *candidate pool* (default 72 hours). Before any role is accepted, its employer ATS must confirm a current listing and an actual published age of no more than 21 days. Unknown publication age is grounds for exclusion.
3. **Career fit beats keyword matching:** Exclude technical/architecture roles, BDR/SDR/inside-sales supervision, creator/influencer marketing, specialized healthcare/biotech, traditional procurement/sourcing/SCM and other materially different tracks. Employer-specific requirements are screened after fetching the full description. An automated pass is not a substitute for individual interpretation.
4. **Reduce repeated applications:** Compare against `applied.csv` for exact URL or similar role/title, and temporarily cool down Datadog, Okta, Via, Stripe, DoorDash, Ramp and Databricks. This is not a lifetime blacklist.
5. **Preserve honesty:** Employer posting date, location, and full job description are verified from the employer ATS. If an ATS cannot be verified or lacks a reliable age, record the reason and do not recommend it as open.
6. **Prioritize:** Recommend up to 15 verified roles from different companies, grouped as Strong/Good. More granular human-level experience assessment is still needed before treating a recommendation as a guaranteed match.
7. **No auto-apply:** V3 does not access applicant credentials, fill forms or submit applications. The separate Greenhouse approval-gated workflow is unchanged.

## Current data-quality limitations

- `applied.csv` contains a small, incomplete sample of application history, not all historical applications. A 13-row tracker must not be represented as a comprehensive record of 300+ applications. The seven repeatedly applied-to employers are cooled down independently as a temporary safeguard.
- ATS verification is implemented for Greenhouse, Lever, Ashby and Workday. Other providers are discovered but withheld from the verified shortlist until an official-site verifier is added.
- The feed may have incomplete, delayed, or incorrectly categorized company/location data. Employer descriptions are the source of truth where available, and unverified information must not be invented.
- Output fit explanations are conservative and rules-based; real requirements should be reviewed for high-stakes roles.

## Run

Install dependencies with `pip install -r requirements.txt`.

Run tests: `python -m unittest test_verified_search_v3 test_deliver_verified_v3 -v`.

Dry-run live sourcing and verification: `python verified_search_v3.py --hours 72 --verify 110 --limit 15`.

Outputs: `verified_shortlist_v3.json`, `verified_shortlist_v3.html`, with a comprehensive exclusion-reason counter.

Preview email without sending: `python deliver_verified_v3.py`.

Email is possible only with explicit `--send` and secrets already configured. Successful SMTP delivery is recorded in a separate `verified_history_v3.json`. The v3 acceptance workflow does **not** send emails or perform submissions.

## Next steps for production

- Validate v3 live shortlist quality and rerun relevant tests.
- Switch the daily scheduled workflow from v2 to v3 (and restore persistent v3 email history).
- Import fuller application history **privately** rather than publishing detailed personal application data to a public repository.
- Add verified site checks for more ATS providers and explicit qualification-gap detection.
