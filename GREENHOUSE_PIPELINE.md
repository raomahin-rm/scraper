# Greenhouse application pipeline

Code lives on `phase1-scraper-development`; the existing
`application-queue-v2.yml` entry point lives on `main` and checks out that branch.
This runner never accepts the old queue's `approved` status as permission to send.

## Supported tonight

* Direct HTTPS Greenhouse `/board/jobs/id` pages; custom employer domains,
  embedded redirects, Workday and Ashby are explicitly unsupported.
* Restore the existing queue, shortlist and tailored drafts from Actions artifacts.
* Fetch the current description and field schema; screen commercial role,
  geography and explicit sponsorship/citizenship restrictions. Extract requirements
  for review rather than claiming that a title match proves qualifications.
* Generate employer-specific motivation and accepted TXT cover-letter drafts from
  the description and verified commercial evidence, retaining the previous draft.
* Fill text, native selects, React selects, checkboxes and file controls using
  Playwright with readback. Discover extra required live controls. Missing answers,
  consent, demographic questions and employer-specific tenure are never guessed.
* Preview blocks all non-read HTTP methods, including employer uploads and
  telemetry. It never clicks Submit. Resumes are hashed and prepared privately;
  file uploads are deferred until individual approval, then attached and verified
  before the submission click.
* Submission requires an exact owner-authored GitHub comment for one packet,
  posted after preparation, valid for 24 hours. The digest binds job description,
  answers, option schema, inspected live controls, review errors, and document
  bytes. A fresh description/schema and approval check runs immediately before
  submission. CAPTCHA is never solved or bypassed; uncertain outcomes require
  manual reconciliation.
* Before clicking, reserve the canonical board/job in the durable
  `application-submission-ledger` branch. A crash or canceled workflow leaves the
  reservation, so neither aliases nor retries can silently submit twice.
* Only a visible employer confirmation marks the queue submitted. Timeouts are
  recorded as `submission_unknown`. Preparation and browser errors are recorded
  by type without exposing private values in logs.

## Commands

Install `requirements.txt`, then `python -m playwright install chromium`.

```sh
python greenhouse_pipeline_v3.py prepare --source runtime/restored --output runtime/greenhouse
python greenhouse_pipeline_v3.py fill --packet runtime/greenhouse/ID/packet.json --db runtime/greenhouse/applications_v2.json --output runtime/greenhouse/ID/live
```

Optional private preparation inputs: `--contact-json` (field ID to value),
`--overrides-json` (application ID to field ID/value mapping), and `--resume`.
Use observed employer option labels exactly. Resolve unknown controls from the
live form, update inputs and prepare/fill again. Review the actual form and the
`review.md`, cover letter and resume bytes. Review-only drafts are not silently
inserted into arbitrary employer questions.

Approval is a user-authored comment on a repository issue or PR:

```
I APPROVE SUBMIT APPLICATION_ID FULL_PACKET_SHA256
```

The runner retrieves that comment from GitHub itself; it cannot be replaced with
an arbitrary local approval file, actor flag, blanket approval or old queue state.
Do not create that comment on the user's behalf.

```sh
GH_TOKEN=... python greenhouse_pipeline_v3.py submit --packet runtime/greenhouse/ID/packet.json --db runtime/greenhouse/applications_v2.json --output runtime/greenhouse/ID/live --approval-comment COMMENT_ID
```

The ledger branch must already exist. Submission fails closed if journal access,
reviewed documents, approval or required fields are unavailable. It does not
silently start a new application queue when restoration fails.

## Actions

The existing workflow has `prepare`, `fill` and `submit` modes. `fill` takes one
existing application ID. `submit` restores the exact `greenhouse-pipeline`
artifact from `packet_run_id` and verifies `approval_comment_id`.

Private inputs can be supplied by repository secrets `APPLICATION_CONTACT_JSON`,
`APPLICATION_OVERRIDES_JSON`, and `APPLICATION_RESUME_BASE64`. Runtime material
must not be committed. Do not enable private inputs without artifact encryption
(`APPLICATION_PACKET_KEY`; see workflow). Browser screenshots remain internal
and are not published as artifacts.

## Validation and limits

`python -m unittest discover -p 'test_*.py'` covers the existing suite plus approval,
changed materials, unsupported URLs, restrictions, missing answers, duplicates,
unknown outcomes and error persistence. `RUN_BROWSER_TESTS=1 python -m unittest
test_greenhouse_browser_v3 -v` tests actual Chromium text/select/checkbox/file
controls and new required-field discovery against a local fixture without sending.
The fill workflow exercises the real selected employer form without submission.

No real employer submission is tested until the user explicitly approves one
complete application. Dynamic location/education widgets and multiselects may need
employer-specific handling. Current-only sponsorship, privacy acknowledgements,
prior employer history and demographic choices require individual answers.
Private document uploads are deferred until individual approval. Actual file
controls are tested with Chromium fixtures; employer uploads and the final
submission click remain unverified on a live employer until an application is
approved. This is not proof of an accepted real application.
