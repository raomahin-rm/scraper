"""Generate a local HTML preview of ranked jobs; never sends email."""
import argparse
import html
import json
from pathlib import Path

def render(payload):
    rows = []
    for j in payload.get("top", []):
        title = html.escape(str(j.get("title", "")))
        company = html.escape(str(j.get("company", "")))
        location = html.escape(str(j.get("location", "")))
        url = html.escape(str(j.get("url", "")), quote=True)
        score = html.escape(str(j.get("score", "")))
        rows.append(f'<tr><td><a href="{url}">{title}</a></td><td>{company}</td><td>{location}</td><td>{score}</td></tr>')
    table = "".join(rows) or '<tr><td colspan="4">No eligible jobs found</td></tr>'
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Job shortlist preview</title>'
            '<style>body{font-family:Arial,sans-serif;max-width:1100px;margin:35px auto;color:#222}'
            'table{border-collapse:collapse;width:100%}th,td{padding:11px;border-bottom:1px solid #ddd;text-align:left}'
            'th{background:#f3f4f6}a{color:#1354a4}</style></head><body>'
            '<h1>Daily job shortlist — preview only</h1><p>No emails were sent. '
            'Location-ambiguous roles are excluded from this preview.</p>'
            f'<p>US matches: {int(payload.get("total_us_matches",0))} | '
            f'Location review: {int(payload.get("total_location_review",0))}</p>'
            '<table><thead><tr><th>Position</th><th>Company</th><th>Location</th><th>Score</th>'
            '</tr></thead><tbody>' + table + '</tbody></table></body></html>')

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="v2_shortlist.json")
    p.add_argument("--output",default="v2_email_preview.html")
    a=p.parse_args()
    payload=json.loads(Path(a.input).read_text(encoding="utf-8"))
    Path(a.output).write_text(render(payload),encoding="utf-8")
    print("Preview created:",a.output,"jobs:",len(payload.get("top",[])))

if __name__=="__main__":
    main()
