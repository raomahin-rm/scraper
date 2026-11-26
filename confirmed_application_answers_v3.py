"""Decrypt the owner's confirmed application facts on the GitHub runner.

Only the public-key-encrypted payload is stored in the repository.
The existing resume/contact bundle is never overwritten.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from greenhouse_private_v3 import KEYRING, get_file, open_bundle

CONFIRMED = "private-materials/confirmed-answers-2026-11-25.enc.json"
ALLOWED_POLICIES = {
    "prior_employment_at_named_employers",
    "restrictive_agreements",
    "salary_preference",
    "voluntary_demographics",
    "recruiter_sms",
    "privacy_and_recording",
    "specialized_experience",
}
VALID = {
    "prior_employment_at_named_employers": ("none",),
    "restrictive_agreements": ("none",),
    "salary_preference": ("advertised_range_midpoint",),
    "voluntary_demographics": ("individual_review",),
    "recruiter_sms": ("yes",),
    "privacy_and_recording": ("individual_review",),
    "specialized_experience": ("none",),
}

def restore_confirmed_answers(output):
    ring = get_file(KEYRING)
    bundle = get_file(CONFIRMED)
    if ring is None or bundle is None:
        raise ValueError("Encrypted confirmed answers unavailable")
    with tempfile.TemporaryDirectory() as directory:
        restored = open_bundle(ring, bundle, os.environ.get("GREENHOUSE_WRAPPING_SECRET",""), directory)
        if restored != ["overrides.json"]:
            raise ValueError("Unexpected confirmed-answer payload shape")
        data = json.loads((Path(directory) / "overrides.json").read_text())
    policy = data.get("__confirmed_policy__")
    if (not isinstance(policy, dict) or set(policy) != ALLOWED_POLICIES
            or any(policy.get(k) not in VALID[k] for k in ALLOWED_POLICIES)):
        raise ValueError("Confirmed answers failed strict validation")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(policy), encoding="utf-8")
    output.chmod(0o600)
    print("Decrypted",len(policy),"confirmed private answer policies; no individual values logged")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="runtime/private/confirmed-answers.json")
    args=p.parse_args()
    restore_confirmed_answers(args.output)
