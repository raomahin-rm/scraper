"""Summarize audited ATS feeds without assuming untested companies work."""
import argparse
import csv
from collections import Counter
from pathlib import Path

def summarize(rows):
    status = Counter(r["status"] for r in rows)
    by_ats = {}
    for r in rows:
        ats = r["ats"]
        by_ats.setdefault(ats, Counter())[r["status"]] += 1
    lines = ["# Company feed audit", "", f"Entries audited: {len(rows)}", ""]
    lines += ["## Status", "", "| Status | Count |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in sorted(status.items())]
    lines += ["", "## ATS breakdown", "", "| ATS | Verified | Reachable empty | Failed | Unconfigured |", "|---|---:|---:|---:|---:|"]
    for ats, c in sorted(by_ats.items()):
        lines.append(f"| {ats} | {c['verified']} | {c['reachable_empty']} | {c['failed']} | {c['not_configured']} |")
    for key in ("failed", "not_configured", "reachable_empty"):
        subset = [r for r in rows if r["status"] == key]
        lines += ["", f"## {key.replace('_',' ').title()} ({len(subset)})", ""]
        for r in subset:
            lines.append(f"- {r['name']} ({r['ats']}): {r.get('error') or r.get('http_status') or 'No configured endpoint'}")
    return "\n".join(lines) + "\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="feed_audit.csv")
    p.add_argument("--output",default="feed_audit_summary.md")
    a=p.parse_args()
    with Path(a.input).open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    report=summarize(rows)
    Path(a.output).write_text(report,encoding="utf-8")
    print("\n".join(report.splitlines()[:24]))
if __name__=="__main__":
    main()
