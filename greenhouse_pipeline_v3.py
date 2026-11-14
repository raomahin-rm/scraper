"""Greenhouse preparation and browser runner. No submission without owner approval.

Runtime files (including contact details, resumes and screenshots) MUST stay private.
The old queue's approved flag is deliberately not accepted as submission permission.
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from application_queue_v2 import load, save
from application_answers_v2 import draft
from employer_questions_v2 import greenhouse_parts, API, extract_questions
from employer_answer_matches_v2 import SENSITIVE
from rank_v2 import evaluate

REPO = "raomahin-rm/scraper"
OWNER = "raomahin-rm"
VERSION = 1
CONFIRMATION_PATTERN = re.compile(r"^(?:(?:your )?application (?:has been (?:received|submitted)|(?:was )?(?:successfully )?submitted|received)|thank you(?: for applying(?: to .+)?| for your application)?|successfully submitted)[.!\s]*$", re.I)

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def text_content(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(raw or "")))).strip()

def fetch_job(url, session=requests):
    parts = greenhouse_parts(url)
    if not parts:
        raise ValueError("Unsupported ATS: requires a direct Greenhouse board/job URL")
    r = session.get(API.format(board=parts[0], job_id=parts[1]), timeout=30)
    r.raise_for_status()
    job = r.json()
    if str(job.get("id")) != parts[1] or not job.get("title") or not job.get("content"):
        raise ValueError("Closed or mismatched job response")
    return job

def job_fingerprint(job):
    # Location, title, full job description and all form/consent schemas are bound.
    return digest({k: job.get(k) for k in ("id", "title", "location", "content", "questions", "location_questions", "compliance", "demographic_questions", "data_compliance")})

def screen(app, job):
    description = text_content(job["content"])
    ranked, reason = evaluate(dict(app, title=job["title"], location=job.get("location", {}).get("name", app.get("location", "")), description=description))
    sentences = re.split(r"(?<=[.!?])\s+|[•\n]", description)
    requirements = [s for s in sentences if re.search(r"\b(require|must|years|experience|proficien|eligible|sponsor|clearance|citizen)\w*\b", s, re.I)]
    hard = [s for s in sentences if re.search(r"(?:cannot|unable to|do not|does not|will not|no)\s+(?:provide\s+|offer\s+)?(?:visa\s+)?sponsor|(?:must be|requires?) (?:a )?(?:u\.?s\.? citizen|security clearance)", s, re.I)]
    return {"decision": "blocked" if not ranked or hard else "review", "title_screen": reason,
            "score": ranked.get("score") if ranked else None,
            "requirements_for_review": requirements, "hard_restrictions": hard,
            "note": "Description screened; industry tenure, years and eligibility are not inferred from title matching."}

def suggested(question, bank):
    label = question["label"]
    if SENSITIVE.search(label):
        return None, "demographic_individual_review"
    if re.search(r"privacy|acknowledg|consent|certif|attest|terms|have you worked|previous.*employ|artificial intelligence|\bAI\b", label, re.I):
        return None, "consent_or_history_individual_review"
    answer = draft(label, bank)
    category = answer["category"]
    # Generic Yes is unsafe for current-only, negated, foreign or combined wording.
    if category == "work_authorization" and (not re.search(r"United States|\bU\.?S\.?\b", label, re.I) or re.search(r"not|without|unrestricted|permanent|indefinite", label, re.I)):
        return None, "authorization_wording_review"
    if category == "sponsorship" and (re.search(r"\bnow\b|\bcurrently\b|\bnot\b|without", label, re.I) and not re.search(r"future", label, re.I)):
        return None, "current_sponsorship_wording_review"
    if category in {"salary", "years_experience", "revenue_pnl", "enterprise_accounts_contracts", "cold_outreach_quota"}:
        return None, "role_specific_evidence_review"
    return answer["suggested_answer"], answer["reason"]

def tailor(app, job, previous, profile):
    description = text_content(job["content"])
    evidence = profile.get("verified_experience", [])
    themes = [t for t in ("account management", "enterprise", "cross-sell", "upsell", "partnership", "supplier", "category", "pipeline", "negotiat") if t in description.lower()]
    relevant = []
    for item in evidence:
        if any(t in (item.get("evidence", "") + " " + item.get("role", "")).lower() for t in themes):
            relevant.append(f"At {item['employer']}, my experience included {item['evidence']}.")
    if not relevant:
        relevant = [f"At {e['employer']}, my experience included {e['evidence']}." for e in evidence[1:3]]
    focus = "; ".join(themes[:5]) or "commercial execution"
    motivation = (f"The {app['title']} role at {app['company']} interests me because the job description emphasizes {focus}. " + " ".join(relevant[:3]) + " I would bring that experience to understanding customer priorities, structuring commercial opportunities and coordinating execution across teams.")
    letter = f"Dear {app['company']} Hiring Team,\n\nI am applying for the {app['title']} position.\n\n{motivation}\n\nI would welcome a conversation about the team's priorities and how my experience could contribute.\n\nBest regards,\nRao Mahin\n"
    return {"why_company_draft": motivation, "cover_letter_text": letter,
            "source_draft": previous, "job_description_themes": themes,
            "evidence_sources": relevant, "requires_individual_review": True}

def prepare(app, job, bank, previous, profile, contact=None, overrides=None, documents=None):
    contact, overrides, documents = contact or {}, overrides or {}, documents or {}
    answers, pending = [], []
    questions = extract_questions(job)
    for question in questions:
        alternatives = question["fields"]
        # Prefer private file over alternate resume_text; no empty placeholder files.
        field = next((f for f in alternatives if f["type"] == "input_file" and f["name"] in documents), alternatives[0] if alternatives else None)
        if not field:
            pending.append(question["label"] + ": unsupported field schema")
            continue
        name = field["name"]
        value, source = suggested(question, bank)
        if name in contact:
            value, source = contact[name], "private_contact"
        if name in overrides:
            value, source = overrides[name], "individual_answer_for_review"
        if name in documents:
            value, source = str(Path(documents[name]).resolve()), "private_document"
        if source == "private_document" and not Path(value).is_file():
            raise ValueError("Document unavailable: " + name)
        allowed = field.get("values", [])
        if value is not None and allowed and str(value) not in [str(x["label"]) for x in allowed]:
            value, source = None, "answer_not_in_employer_options"
        if question["required"] and value in (None, ""):
            pending.append(question["label"])
        answers.append({"name": name, "label": question["label"], "required": question["required"],
                        "type": field["type"], "options": allowed, "value": value, "source": source})
    # DOM-only fields are explicit overrides, discovered by the browser runner.
    known = {a["name"] for a in answers}
    for name, value in {**contact, **overrides}.items():
        if name not in known:
            answers.append({"name": name, "label": name, "required": False, "type": "dom", "value": value, "source": "individual_answer_for_review"})
    docs = {k: {"path": str(Path(v).resolve()), "sha256": file_hash(v)} for k, v in documents.items()}
    return {"version": VERSION, "id": app["id"], "company": app["company"], "title": job["title"], "url": app["url"],
            "job_fingerprint": job_fingerprint(job), "screening": screen(app, job),
            "answers": answers, "documents": docs, "missing_required": pending,
            "drafts": tailor(dict(app, title=job["title"]), job, previous, profile), "prepared_at": now(),
            "status": "needs_review", "submitted": False}

def approval_digest(packet):
    # Hash actual content, never timestamps or local paths.
    return digest({k: packet[k] for k in ("version", "id", "company", "title", "url", "job_fingerprint", "screening")} | {
        "answers": [{k: a.get(k) for k in ("name", "label", "type", "value", "options")} for a in packet["answers"] if a["type"] != "input_file"],
        "documents": {k: v["sha256"] for k, v in packet["documents"].items()},
        "drafts": packet["drafts"], "missing_required": packet["missing_required"], "live_schema": packet.get("live_schema"), "live_review": packet.get("live_review")})

def validate_approval(packet, comment, owner=OWNER):
    if not packet.get("live_schema"):
        raise ValueError("Live form must be inspected and filled before approval")
    expected = f"I APPROVE SUBMIT {packet['id']} {approval_digest(packet)}"
    if comment.get("user", {}).get("login") != owner or comment.get("body", "").strip() != expected:
        raise ValueError("Explicit individual owner approval for this exact packet is required")
    created = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
    if created < datetime.fromisoformat(packet["prepared_at"]) or created < datetime.now(timezone.utc) - timedelta(hours=24) or created > datetime.now(timezone.utc):
        raise ValueError("Approval expired or predates preparation")
    if packet.get("live_review", {}).get("errors") or packet.get("live_review", {}).get("unresolved_live_fields"):
        raise ValueError("Live form has unresolved fields or fill errors")
    if packet["missing_required"] or packet["screening"]["decision"] == "blocked":
        raise ValueError("Application has unresolved required answers or screening restrictions")
    return {"comment_id": comment["id"], "actor": owner, "packet_digest": approval_digest(packet), "at": created.isoformat()}

def fetch_approval(comment_id, session=requests):
    if not str(comment_id).isdigit():
        raise ValueError("A numeric owner-authored GitHub issue comment ID is required")
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    r = session.get(f"https://api.github.com/repos/{REPO}/issues/comments/{comment_id}", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def event(db, uid, state, **details):
    app = db["applications"][uid]
    app.setdefault("events", []).append({"status": state, "at": now(), **details})
    app["pipeline_status"] = state

def check_duplicate(db, packet):
    parts = greenhouse_parts(packet["url"])
    for app in db["applications"].values():
        if (app["id"] == packet["id"] or greenhouse_parts(app["url"]) == parts) and (
            app.get("status") == "submitted" or any(e["status"] in {"submission_started", "submission_unknown", "submitted"} for e in app.get("events", []))):
            raise ValueError("Prior submission or uncertain attempt exists; reconcile manually before retry")

def assert_documents(packet):
    for doc in packet["documents"].values():
        if file_hash(doc["path"]) != doc["sha256"]:
            raise ValueError("Document changed after review")

LEDGER_BRANCH = "application-submission-ledger"

def durable_attempt(packet, approval, result=None, session=requests):
    """Reserve once in GitHub BEFORE clicking. Unknown outcomes cannot be retried.

    The ledger contains identifiers/hashes only, not applicant answers or documents.
    A reservation is intentionally never deleted, even when an attempt fails.
    """
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise ValueError("Durable submission journal requires GH_TOKEN; refusing submission")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}
    root = f"https://api.github.com/repos/{REPO}"
    board, job_id = greenhouse_parts(packet["url"])
    url = f"{root}/contents/application-attempts/{board}-{job_id}.json"
    current = session.get(url, params={"ref": LEDGER_BRANCH}, headers=headers, timeout=30)
    if result is None:
        if current.status_code != 404:
            if current.status_code == 200:
                raise ValueError("Durable journal already contains an attempt; reconcile manually")
            current.raise_for_status()
        # Branch must be provisioned explicitly; never interpret an absent branch as empty history.
        ref = session.get(f"{root}/git/ref/heads/{LEDGER_BRANCH}", headers=headers, timeout=30)
        ref.raise_for_status()
        payload = {"id": packet["id"], "board": board, "job_id": job_id,
                   "packet_digest": approval["packet_digest"], "approval_comment_id": approval["comment_id"],
                   "state": "submission_started", "at": now()}
        body = {"message": f"Reserve approved application {packet['id']}", "branch": LEDGER_BRANCH,
                "content": base64.b64encode((json.dumps(payload, indent=2)+"\n").encode()).decode()}
    else:
        current.raise_for_status()
        previous = json.loads(base64.b64decode(current.json()["content"]))
        if previous["packet_digest"] != approval["packet_digest"]:
            raise ValueError("Journal packet mismatch")
        previous.update(state="submitted" if result.get("submitted") else "submission_unknown", updated_at=now())
        body = {"message": f"Record application outcome {packet['id']}", "branch": LEDGER_BRANCH,
                "sha": current.json()["sha"], "content": base64.b64encode((json.dumps(previous,indent=2)+"\n").encode()).decode()}
    response = session.put(url, headers=headers, json=body, timeout=30)
    response.raise_for_status()
    return response.json()

def control(page, name):
    # IDs observed on current and legacy Greenhouse forms. Exact matching only.
    return page.locator(f'[id={json.dumps(name)}], [name={json.dumps(name)}]').first

def fill_value(page, answer):
    value, name = answer.get("value"), answer["name"]
    if value is None:
        return False
    loc = control(page, name)
    if not loc.count():
        raise ValueError("Field not found: " + name)
    tag = loc.evaluate("e=>e.tagName.toLowerCase()")
    typ = loc.get_attribute("type")
    if typ == "file":
        loc.set_input_files(value)
        # Greenhouse uploads asynchronously; confirm uploaded filename in form.
        page.get_by_text(Path(value).name, exact=True).first.wait_for(timeout=30000)
    elif tag == "select":
        loc.select_option(label=str(value))
        if loc.locator("option:checked").inner_text() != str(value):
            raise ValueError("Select readback mismatch: " + name)
    elif typ in {"checkbox", "radio"}:
        if not isinstance(value, bool):
            raise ValueError("Checkbox requires an explicit boolean")
        loc.set_checked(value)
        if loc.is_checked() != value:
            raise ValueError("Checkbox readback mismatch")
    elif loc.get_attribute("role") == "combobox":
        from playwright.sync_api import expect
        loc.click()
        option = page.get_by_role("option", name=str(value), exact=True)
        try:
            expect(option).to_have_count(1, timeout=2000)
            option.wait_for(timeout=2000)
        except Exception:
            # Geocoders can return two identically labelled places for a full
            # address query. Search by city, then still require one exact label.
            query = str(value).split(",", 1)[0] if name == "candidate-location" else str(value)
            loc.fill(query)
            expect(option).to_have_count(1, timeout=15000)
            option.wait_for(timeout=15000)
        if option.count() != 1:
            raise ValueError("Ambiguous dropdown option: " + name)
        option.click()
        # React Select keeps chosen label beside input, whose value is cleared.
        selected = loc.locator("xpath=ancestor::*[contains(@class,'select__control')][1]")
        if selected.count() != 1:
            raise ValueError("Dropdown readback container missing: " + name)
        if str(value) not in selected.inner_text():
            # Country controls display only a flag and dial code. Verify the
            # exact option remains selected rather than guessing from +1.
            loc.click()
            chosen = page.get_by_role("option", name=str(value), exact=True)
            chosen.wait_for(timeout=5000)
            if chosen.get_attribute("aria-selected") != "true":
                raise ValueError("Dropdown readback mismatch: " + name)
            loc.press("Escape")
    else:
        loc.fill(str(value))
        if loc.input_value() != str(value):
            raise ValueError("Text readback mismatch: " + name)
    return True

def live_fields(page):
    return page.locator('form input, form select, form textarea, [data-testid="application-form"] input').evaluate_all('''es=>es.filter(e=>e.id && e.type!=='hidden' && e.type!=='file' && !e.id.startsWith('g-recaptcha')).map(e=>({id:e.id,type:e.type,required:e.required||e.getAttribute('aria-required')==='true',label:e.labels?.[0]?.innerText||e.getAttribute('aria-label')||e.id}))''')

def fill_form(page, packet, defer_files=False):
    errors, filled, deferred, skipped = [], [], [], []
    # Uploads/SSR hydration can replace controlled inputs. Attach first, then
    # populate contact/answer fields after the upload UI has initialized.
    ordered = sorted(packet["answers"], key=lambda a: 0 if a.get("type") == "input_file" else 1) if not defer_files else packet["answers"]
    for answer in ordered:
        if answer.get("type") == "dom" and not answer.get("required") and not control(page, answer["name"]).count():
            skipped.append(answer["name"])
            continue
        if defer_files and answer.get("type") == "input_file" and answer.get("value"):
            deferred.append(answer["name"])
            continue
        try:
            if fill_value(page, answer):
                filled.append(answer["name"])
        except Exception as exc:
            # Do not put field values, contacts, Playwright dumps or URLs with tokens in logs.
            errors.append({"field": answer["name"], "error_type": type(exc).__name__})
    repaired = []
    # Reconcile controlled text inputs after all async document/widget changes.
    # Never infer missing values: restore only the exact reviewed packet value.
    for answer in packet["answers"]:
        if answer.get("value") is None or answer.get("type") == "input_file":
            continue
        loc = control(page, answer["name"])
        if not loc.count() or loc.get_attribute("role") == "combobox":
            continue
        typ = loc.get_attribute("type")
        if typ in {"checkbox", "radio", "hidden", "file"}:
            continue
        try:
            if loc.input_value() != str(answer["value"]):
                loc.fill(str(answer["value"]))
                loc.press("Tab")
                if loc.input_value() != str(answer["value"]):
                    raise ValueError("Final text reconciliation failed")
                repaired.append(answer["name"])
        except Exception as exc:
            errors.append({"field": answer["name"], "error_type": type(exc).__name__})
    known = {a["name"] for a in packet["answers"] if a.get("value") is not None}
    missing = [f for f in live_fields(page) if f["required"] and f["id"] not in known]
    return {"filled_fields": filled, "repaired_fields": repaired, "deferred_document_uploads": deferred, "skipped_unavailable_optional_fields": skipped, "errors": errors, "unresolved_live_fields": missing,
            "missing_required": packet["missing_required"], "submitted": False}

def allow_preview_request(method, url, documents):
    # Preparation never sends applications, telemetry or attachments to the employer.
    return method in {"GET", "HEAD", "OPTIONS"}

def run_browser(packet, db_path, output, submit=False, approval_comment=None):
    from playwright.sync_api import sync_playwright
    db = load(db_path)
    check_duplicate(db, packet)
    assert_documents(packet)
    approval = None
    if submit:
        approval = validate_approval(packet, fetch_approval(approval_comment))
    live = fetch_job(packet["url"])
    if job_fingerprint(live) != packet["job_fingerprint"]:
        raise ValueError("Job description or form changed; prepare and obtain new approval")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    result = {"id": packet["id"], "submitted": False}
    try:
        with sync_playwright() as p:
            kwargs = {"headless": True}
            if os.environ.get("CHROMIUM_PATH"):
                kwargs["executable_path"] = os.environ["CHROMIUM_PATH"]
            browser = p.chromium.launch(**kwargs)
            context = browser.new_context()
            # Preview mode blocks ALL mutating requests; uploads need submit mode approval.
            # For a fill-only attachment test use text alternatives or approval-controlled submit.
            blocked = []
            def guard(route):
                if not submit and not allow_preview_request(route.request.method, route.request.url, packet["documents"]):
                    blocked.append({"method": route.request.method, "host": urlparse(route.request.url).hostname})
                    route.abort()
                else:
                    route.continue_()
            context.route("**/*", guard)
            page = context.new_page()
            page.goto(packet["url"], wait_until="domcontentloaded", timeout=60000)
            if greenhouse_parts(page.url) != greenhouse_parts(packet["url"]):
                raise ValueError("Application redirected to a different job")
            page.locator('input[id="first_name"]').wait_for(timeout=30000)
            schema = live_fields(page)
            if submit and schema != packet.get("live_schema"):
                raise ValueError("Live form changed after review; new approval required")
            result.update(fill_form(page, packet, defer_files=not submit))
            if not submit:
                packet["live_schema"] = schema
                packet["live_review"] = {"errors": result["errors"], "unresolved_live_fields": result["unresolved_live_fields"]}
                complete = not (result["errors"] or result["unresolved_live_fields"] or packet["missing_required"] or packet["screening"]["decision"] == "blocked")
                packet["status"] = "ready_for_review" if complete else "needs_review"
                if complete and db["applications"][packet["id"]]["status"] == "draft":
                    db["applications"][packet["id"]]["status"] = "ready_for_review"
            result["blocked_mutations"] = blocked
            result["packet_digest"] = approval_digest(packet)
            page.screenshot(path=str(output / "filled-form.png"), full_page=True)
            if submit:
                if result["errors"] or result["unresolved_live_fields"] or result["missing_required"]:
                    raise ValueError("Live form has unresolved fields; submission blocked")
                # Refresh approval at the last possible moment; edits/revocation are respected.
                validate_approval(packet, fetch_approval(approval_comment))
                assert_documents(packet)
                event(db, packet["id"], "submission_started", approval=approval)
                save(db_path, db)  # Persist before click: crash/timeout is NEVER auto-retried.
                durable_attempt(packet, approval)
                page.get_by_role("button", name="Submit application", exact=True).click()
                page.locator('input[id="first_name"]').wait_for(state="hidden", timeout=30000)
                confirmation = page.get_by_text(CONFIRMATION_PATTERN).first
                confirmation.wait_for(timeout=30000)
                result.update(submitted=True, confirmation=confirmation.inner_text(), confirmed_url=page.url)
                app = db["applications"][packet["id"]]
                app.update(status="submitted", confirmation=result["confirmation"], submitted_at=now())
                event(db, packet["id"], "submitted", confirmation=result["confirmation"], approval=approval)
                save(db_path, db)
                try:
                    durable_attempt(packet, approval, result)
                except Exception as exc:
                    result["journal_update_error"] = type(exc).__name__
                    event(db, packet["id"], "submitted", journal_update_error=type(exc).__name__)
            else:
                event(db, packet["id"], "prefilled_for_review", filled_fields=result["filled_fields"], errors=result["errors"], unresolved_live_fields=result["unresolved_live_fields"])
            browser.close()
    except Exception as exc:
        started = db["applications"][packet["id"]].get("pipeline_status") == "submission_started"
        event(db, packet["id"], "submission_unknown" if started else "error", error_type=type(exc).__name__)
        result.update(error_type=type(exc).__name__, status="submission_unknown" if started else "error")
        raise
    finally:
        save(db_path, db)
        save(output / "result.json", result)
        save(output / "result.public.json", public_summary(packet, result))
    return result

def public_summary(packet, result):
    """Publish control/schema evidence without contact details or answer values."""
    return {"id": packet["id"], "company": packet["company"], "title": packet["title"],
            "status": "submitted" if result.get("submitted") else result.get("status", packet.get("status")), "packet_digest": approval_digest(packet),
            "filled_fields": result.get("filled_fields", []),
            "deferred_document_uploads": result.get("deferred_document_uploads", []),
            "errors": result.get("errors", []), "missing_required": packet["missing_required"],
            "live_schema": packet.get("live_schema", []),
            "live_review": packet.get("live_review", {}),
            "job_fingerprint": packet["job_fingerprint"], "prepared_at": packet["prepared_at"],
            "submitted": result.get("submitted", False)}

def execute(packet, db_path, output, submit=False, approval_comment=None):
    try:
        return run_browser(packet, db_path, output, submit, approval_comment)
    except Exception as exc:
        db = load(db_path)
        if packet["id"] in db["applications"]:
            state = db["applications"][packet["id"]].get("pipeline_status")
            if state not in {"submission_unknown", "submitted"}:
                event(db, packet["id"], "error", error_type=type(exc).__name__)
                save(db_path, db)
        raise

def batch(source, output, contact=None, overrides=None, documents=None):
    source, output = Path(source), Path(output)
    db = load(source / "applications_v2.json")
    if not db["applications"]:
        raise ValueError("Existing queue is missing/empty; refusing to rebuild application history")
    bank = json.loads(Path("application_answers_v2.json").read_text())
    profile = json.loads(Path("commercial_profile_v2.json").read_text())
    previous = {d["id"]: d for d in json.loads((source / "tailored_application_drafts_v2.json").read_text())["drafts"]}
    rows = []
    for app in db["applications"].values():
        if app["status"] in {"submitted", "rejected", "withdrawn"}:
            continue
        if not greenhouse_parts(app["url"]):
            rows.append({"id": app["id"], "status": "unsupported_ats"})
            continue
        try:
            job = fetch_job(app["url"])
            app_overrides = dict((overrides or {}).get(app["id"], {}))
            app_documents = app_overrides.pop("_documents", {})
            if not isinstance(app_documents, dict) or not set(app_documents).issubset({"resume", "cover_letter"}):
                raise ValueError("Application documents must map resume/cover_letter to private files")
            packet = prepare(app, job, bank, previous.get(app["id"], {}), profile, contact,
                             app_overrides, {**(documents or {}), **app_documents})
            folder = output / app["id"]
            folder.mkdir(parents=True, exist_ok=True)
            save(folder / "packet.json", packet)
            (folder / "cover-letter.txt").write_text(packet["drafts"]["cover_letter_text"], encoding="utf-8")
            (folder / "review.md").write_text(render_review(packet), encoding="utf-8")
            event(db, app["id"], "prepared_for_review", packet_digest=approval_digest(packet))
            rows.append({"id": app["id"], "company": app["company"], "title": app["title"], "status": packet["screening"]["decision"], "missing_required_count": len(packet["missing_required"]), "digest": approval_digest(packet)})
        except Exception as exc:
            event(db, app["id"], "preparation_error", error_type=type(exc).__name__)
            rows.append({"id": app["id"], "status": "error", "error_type": type(exc).__name__})
    save(output / "applications_v2.json", db)
    save(output / "summary.json", {"applications": rows, "submissions": 0, "prepared_at": now()})
    return rows

def render_review(packet):
    lines = [f"# {packet['company']} — {packet['title']}", "", packet["url"], "", "Status: needs individual review. No submission has occurred.",
             "", "## Description screening", json.dumps(packet["screening"], indent=2), "", "## Exact employer questions and prepared answers"]
    for a in packet["answers"]:
        value = ("Document sha256: " + packet["documents"][a["name"]]["sha256"]) if a["type"] == "input_file" and a.get("value") else a.get("value")
        lines.extend(["", a["label"], "", str(value) if value is not None else "UNANSWERED — individual review required", "", "Source: " + a["source"]])
    lines.extend(["", "## Employer-specific draft", packet["drafts"]["why_company_draft"], "", "## Submission approval", "Review the completed live form and all documents first. Resolve missing fields and prepare again before approving.",
                  "Owner must post this exact individual approval on a repository issue/PR, then supply its comment ID to the submit runner:", "", f"I APPROVE SUBMIT {packet['id']} {approval_digest(packet)}", "", "Approval expires after 24 hours and any material change invalidates it."])
    return "\n".join(lines) + "\n"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "fill", "submit"])
    p.add_argument("--source", default="runtime/restored")
    p.add_argument("--output", default="runtime/greenhouse")
    p.add_argument("--packet")
    p.add_argument("--db")
    p.add_argument("--approval-comment")
    p.add_argument("--contact-json")
    p.add_argument("--overrides-json")
    p.add_argument("--resume")
    p.add_argument("--cover-letter")
    a = p.parse_args()
    if a.action == "prepare":
        read = lambda path: json.loads(Path(path).read_text()) if path else {}
        rows = batch(a.source, a.output, read(a.contact_json), read(a.overrides_json), ({"resume": a.resume} if a.resume else {}) | ({"cover_letter": a.cover_letter} if a.cover_letter else {}))
        from collections import Counter
        print(dict(Counter(r["status"] for r in rows)))
        print("Submissions: 0")
    else:
        if not a.packet or not a.db:
            p.error("--packet and --db required")
        packet = json.loads(Path(a.packet).read_text())
        try:
            result = execute(packet, a.db, a.output, a.action == "submit", a.approval_comment)
        finally:
            if a.action == "fill":
                save(a.packet, packet)
                Path(a.packet).with_name("review.md").write_text(render_review(packet), encoding="utf-8")
        print(json.dumps(public_summary(packet, result)))
        if result.get("errors"):
            raise SystemExit("Form filling encountered errors; inspect result.json")

if __name__ == "__main__":
    main()
