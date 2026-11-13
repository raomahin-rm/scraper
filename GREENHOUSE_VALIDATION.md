# Greenhouse validation — November 13, 2026

No employer applications were submitted. No individual submission approval was
requested or manufactured during testing.

## Reused inputs

* Restored the existing Actions `application-review-queue` artifact from run
  `43466238079`: 48 queue entries, 40-job shortlist and existing tailored drafts.
* Reused `application_answers_v2.json` and `commercial_profile_v2.json`.
* Located the existing approved Commercial Resume, `Rao Mahin(6).pdf`, privately.
  Its bytes and contact details were not committed to GitHub.
* Prepared live description screening, employer question suggestions, motivation
  drafts and accepted TXT cover-letter drafts for all 15 direct Greenhouse URLs.
  The other 33 URLs are explicitly unsupported by this adapter (including custom
  employer domains); they were retained in the queue.

## Real employer test

DoorDash USA: Sr. Enterprise Account Manager, DDfB, job `8255974`, queue ID
`8728b67079744848`.

The first Actions smoke run (`43523806392`) recorded two dropdown TimeoutErrors.
The results were inspected rather than treating the workflow's exit status as
proof of filling. Fixed the adapter to open non-searchable menus before selecting
an exact option; added readback and regression tests. Fill errors now fail CLI/CI.

The corrected run (`43524155025`) executed the actual Playwright runner against
the live employer form. Its result artifact showed:

* `filled_fields`: `question_69640946` (US work authorization),
  `question_69640948` (future sponsorship).
* `errors`: empty; `submitted`: false.
* Non-read requests blocked, including a Recruitics telemetry POST.
* Required unanswered and dynamically discovered fields explicitly reported.

Separately, the live browser verified prefilled name, email, phone, LinkedIn,
United States dialing country and Chicago city controls using the existing resume
and profile. It was left unsubmitted. These browser operations are distinguished
from the automated Actions test, which had no private contact/resume secrets.

## Submission protection and evidence

* Explicit owner-authored approval comment binds one application and packet hash;
  expires after 24 hours. The legacy queue's approved flag cannot authorize sending.
* Fresh description/schema, file hashes and approval are checked again on submit.
* `application-submission-ledger` branch provisioned. A reservation is written
  before clicking; any prior attempt blocks automatic retries.
* Confirmed submissions require visible employer success evidence and the form
  to disappear. Unknown outcomes and errors are persisted, never reported as success.
* Private review artifacts support authenticated encryption. Browser screenshots
  are excluded from uploaded artifacts. Private documents remain outside GitHub.

## Remaining blockers and unverified behavior

* Actions secrets `APPLICATION_CONTACT_JSON`, `APPLICATION_RESUME_BASE64`,
  `APPLICATION_OVERRIDES_JSON`, and `APPLICATION_PACKET_KEY` were empty in the
  observed runner. Private data cannot be attached there until securely configured.
  Existing materials have already been located; they need not be supplied again.
* DoorDash's current-sponsorship wording explicitly includes STEM OPT and requires
  individual review. Prior DoorDash employment, the combined experience question,
  complete-cycle expansion history, privacy acknowledgement, communication consent
  and demographic controls remain unresolved. No demographic answers were inferred.
* No final live resume upload, CAPTCHA, employer submission, confirmation or durable
  journal write has been tested against a real employer because no application has
  been individually approved. File controls were exercised with a local Chromium
  fixture. Journal and encryption behavior have regression tests.
* Multiselects, employer-specific dynamic widgets, custom-domain Greenhouse pages,
  Ashby and Workday are not claimed as fully supported.

## Final test result

Run `43524155025`, attempt 2, checked out code `0749801` and completed successfully:
79 tests discovered (76 passing, 3 browser tests deferred in the initial pass),
then all 3 actual Chromium tests passed separately. The live DoorDash prefill step
also completed successfully. No submit step ran. Both workflow YAML files parse;
`git diff --check` passed. The only subsequent code-branch change is this report.


## Continued development: private-material setup resolved

The Actions runner initialized an RSA keypair protected by an existing Actions
secret, with separate HKDF purposes for private-key wrapping and artifact
protection. Existing resume/contact details and Via-specific answers/cover letter
were sealed to its public key. The workflow successfully decrypted and restored
all four private inputs. No new GitHub sign-in or secret entry was required.

Added regression coverage for envelope tampering, wrong secrets, key integrity,
GitHub's line-wrapped base64 responses, plaintext-free status summaries and async
city-result ambiguity. A Via prefill caught duplicated Chicago search results
and two additional required education controls; the adapter and sealed inputs
were corrected using the existing resume. Voluntary demographic controls remain
unanswered. No application was submitted.


## Final continued-development result

Actions run `43527650336` succeeded using code `58f0d1f`:

* 89 unique tests passed across the offline suite (85) and real Chromium tests (4).
* Via Senior Partner Success Manager: 14 actual live fields filled and read back.
* No fill errors, no missing required API answers, no unresolved required live fields.
* Commercial resume and the Via-specific TXT cover letter restored privately and
  hash-verified; upload is deferred until individual approval.
* Application queue: 47 draft entries and one `ready_for_review` entry.
* Voluntary demographic fields remain blank; zero applications submitted.
* The reconstructed human-readable review packet hash exactly matches the actual
  Actions packet: `e6e8848a51599d04cc095d5fa1b30f8f8f252815f84b154578f97609dffc555c`.

The private-material configuration blocker described earlier is resolved. The
remaining live verification is employer document upload, the submission click,
CAPTCHA if presented, employer confirmation and the durable submission journal's
real outcome. Those steps remain behind explicit individual approval. No such
approval has been received. All prior unsupported ATS limitations still apply.
