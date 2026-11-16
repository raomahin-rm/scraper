# Verified Daily Job Search — V3

This repository now prioritizes **verified, recently published, well-matched U.S. commercial jobs** over large unfiltered batches of links. The scheduled workflow is [Verified daily job shortlist v3](.github/workflows/verified-job-search-v3.yml). The previous V2 email workflow is **manual-only**.

## What it does

- Searches a broad, multi-ATS public feed rather than relying exclusively on a fixed list of 305 employers.
- Only considers fresh feed discoveries as **leads**, never as evidence of when the job was published.
- Checks employer Greenhouse, Lever, Ashby or Workday sources for current availability, complete job text, U.S. location and actual publication date. No confirmed age means no recommendation.
- Screens for commercial partnerships, BD, enterprise accounts, sales leadership, category/vendor management; excludes technical engineering, BDR/SDR, specialist procurement, marketing activation, hard industry gaps and roles with clear sponsorship prohibitions.
- Checks existing application tracking and temporarily reduces repeat recommendations from seven previously overused employers.
- Emails **up to 15** employer-verified positions on the daily schedule, grouped with fit and gap lines; uses persistent deduplication history across runs. Code-change and manual runs do **not** send email.
- **Never submits applications.** Greenhouse application-form workflows remain independent and require explicit individual approval.

## Main code

Source, screening, age verification and HTML audit: [verified_search_v3.py](https://github.com/raomahin-rm/scraper/blob/phase1-scraper-development/verified_search_v3.py).

Opt-in SMTP and persistent dedupe: [deliver_verified_v3.py](https://github.com/raomahin-rm/scraper/blob/phase1-scraper-development/deliver_verified_v3.py).

Tests: [test_verified_search_v3.py](https://github.com/raomahin-rm/scraper/blob/phase1-scraper-development/test_verified_search_v3.py) and [test_deliver_verified_v3.py](https://github.com/raomahin-rm/scraper/blob/phase1-scraper-development/test_deliver_verified_v3.py).

Detailed specification, limitations and third-party credits: [VERIFIED_JOB_SEARCH_V3.md](https://github.com/raomahin-rm/scraper/blob/phase1-scraper-development/VERIFIED_JOB_SEARCH_V3.md).

## Manual read-only verification

```bash
pip install -r requirements.txt
python -m unittest test_verified_search_v3 test_deliver_verified_v3 -v
python verified_search_v3.py --hours 72 --verify 110 --limit 15
python deliver_verified_v3.py
```

The last command only generates an email preview. SMTP requires the explicit `--send` option and configured repository secrets.

## Limits and next improvements

- `applied.csv` is currently **incomplete** and must not be mistaken for the candidate's full application history. The seven-company cooldown is temporary, not a substitute for a complete private tracker.
- Unsupported ATS feeds may yield candidates that are **withheld** because employer verification is unavailable; this is preferable to sending unverified links.
- Automatic qualification screening is not a substitute for reviewing a complex job description. A verified open role may still be a weaker match than the preferred shortlist.
- LinkedIn connection matching and private application-history reconciliation have not yet been integrated.

The v3 discovery design is informed by [Heidi Miller's MIT-licensed Daily Job Search methodology](https://github.com/heidimillerpresents-png/claude-skills/tree/main/daily-job-search) and [Riley Dorrington's public multi-ATS feed](https://github.com/Riley-Dorrington/job-board-data), used as a source of unverified leads. It does not transplant or execute the upstream Claude skill.
