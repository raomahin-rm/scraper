# Daily job scraper

Every morning it checks company career pages (Greenhouse, Lever, Ashby) and
optionally Adzuna, filters to your target titles and level, scores each job,
and emails you the top 25 at raomahin@gmail.com.

## What is in this folder

- `job_scraper.py`  the script
- `config.py`  companies, title rules, locations, scoring. Edit this one.
- `applied.csv`  jobs you already applied to, so they never show up again
- `.github/workflows/daily-jobs.yml`  the daily schedule
- `test_offline.py`  quick test with fake jobs (no internet needed)

## Setup (about 15 minutes)

1. **Make a private GitHub repo** and upload everything in this folder,
   including the hidden `.github` folder. Keep it private because
   `applied.csv` is personal.

2. **Get a Gmail app password.** Google Account > Security. Turn on
   2-Step Verification, then search for "App passwords" and create one.
   You get a 16 character password.

3. **Add secrets.** In the repo: Settings > Secrets and variables > Actions
   > New repository secret. Add:
   - `GMAIL_USER`  raomahin@gmail.com
   - `GMAIL_APP_PASSWORD`  the 16 character password
   - `MAIL_TO`  raomahin@gmail.com (or another address)

   Optional, but worth it:
   - `ANTHROPIC_API_KEY`  turns on the AI fit score (1 to 10) and one-line
     reason per job. This is a separate key from your Claude chat
     subscription. Create it in the Anthropic Console. Cost is small
     (about 40 short calls a day).
   - `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`  free keys from
     developer.adzuna.com. This adds jobs from companies not on your list.

4. **Run it once by hand.** Actions tab > Daily job scan > Run workflow.
   Check your inbox. The footer of the email lists any company slugs that
   failed. Fix or delete those in `config.py`.

5. After that it runs every day at 12:00 UTC (7am Chicago in summer,
   6am in winter).

## Daily use

- Add companies to `GREENHOUSE`, `LEVER` or `ASHBY` in `config.py`. The slug
  is the last part of their careers URL, for example
  `jobs.ashbyhq.com/elevenlabs` gives `elevenlabs`.
- Add jobs you applied to in `applied.csv` (company,title,url).
- If you get too many or too few jobs, change `MIN_SCORE` and `MAX_AGE_HOURS`.
- If a type of job keeps showing up that you do not want, add a word to
  `EXCLUDE_TITLE` or `NEGATIVE_KEYWORDS`.

## Test on your own computer

    pip install -r requirements.txt
    python test_offline.py
    python job_scraper.py --dry-run

The dry run fetches real jobs and writes `preview.html`. It does not send
email or change any saved state.

## What it does not do

- It does not scrape LinkedIn or Indeed. Those block bots and can ban your
  account. If you want LinkedIn jobs, set up LinkedIn job alerts, they email
  you directly.
- It does not apply for you.
