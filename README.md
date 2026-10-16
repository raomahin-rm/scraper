# Daily job scraper (version 2)

Every morning it checks company job feeds and Adzuna, keeps US commercial roles
at Associate to Senior Manager level, scores them, and emails the top 25 to
raomahin@gmail.com.

## What changed in version 2

- US only. Non-US locations are dropped.
- Priority cities: NY, Chicago, LA, SF, Houston, Dallas, Austin, Boston, Atlanta.
  Remote and the rest of the US rank lower.
- Two resumes. Each job says "Commercial resume" or "AI/Tech resume".
- Policy track is off.
- Visa column. Postings that say they will not sponsor are dropped.
  Postings that say they sponsor get a boost. Companies in `sponsors.csv`
  get a smaller boost. Most postings say nothing, so "Unknown" is normal.
- New companies get a bonus. Companies you applied to recently get a penalty
  and a warning.
- At most 2 different roles per company per email. The same role in several cities counts once.
- Titles added: Key Account Manager, Customer Business Manager, Vendor
  Manager, Buyer, Account Executive, Revenue Growth Management.
- 23 target companies get a bonus. Big employers that use Workday or their own
  career sites are searched through Adzuna.

## Files

- `job_scraper.py`  the script
- `config.py`  companies, titles, cities, scoring. Edit this one.
- `applied.csv`  companies and jobs you applied to (columns: company,title,url,date)
- `sponsors.csv`  companies known to file H-1B petitions. A starter list from
  general knowledge, not live data. Replace it with real data when you can.
- `test_offline.py`  quick test with fake jobs
- `.github/workflows/daily-jobs.yml`  the daily schedule

## applied.csv

One row per company is enough. Title, url and date are optional.

    company,title,url,date
    Block,,,
    Stripe,Partnerships Manager,,2026-10-01

A date lets the script warn you when you applied less than 60 days ago.

## Secrets

Add these in GitHub: Settings > Secrets and variables > Actions.

- `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO` (already done)
- `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`: register free at developer.adzuna.com
- `ANTHROPIC_API_KEY`: from console.anthropic.com, turns on the 1 to 10 fit score

Never paste keys into chats or emails.

## Limits

- First run after an update shows jobs from the last 14 days, so you see the backlog. After that each job is emailed once.
- Companies on Workday or their own sites (Google, Amazon, Walmart and others)
  only come through Adzuna. Without Adzuna keys you only see tech companies.
- The visa column is a hint, not a promise. A company on the sponsor list may
  still not sponsor this role.
- It does not scrape LinkedIn or Indeed.
- It does not apply for you.
