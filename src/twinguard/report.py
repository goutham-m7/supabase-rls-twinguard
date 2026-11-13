"""A static, escaped evidence viewer. No server, script, CDN or telemetry."""
from html import escape
import json


def summarize(attempts: list[dict]) -> dict:
    summary = {}
    for attempt in attempts:
        group = summary.setdefault(attempt["control"], {"attempts": 0, "passed": 0, "happy_path": 0,
                                                      "unauthorized_reads": 0, "unauthorized_writes": 0})
        group["attempts"] += 1
        group["passed"] += int(attempt["passed"])
        group["happy_path"] += int(attempt["checks"]["read_repaired"])
        group["unauthorized_reads"] += attempt["unauthorized_reads"]
        group["unauthorized_writes"] += attempt["unauthorized_writes"]
    return summary


def render(attempts: list[dict]) -> str:
    def code(value):
        return "<pre>" + escape(json.dumps(value, indent=2) if not isinstance(value, str) else value) + "</pre>"

    summary_rows = "".join(
        f"<tr><th scope='row'>{escape(label)}</th><td>{s['passed']}/{s['attempts']}</td>"
        f"<td>{s['happy_path']}/{s['attempts']}</td><td>{s['unauthorized_reads']}</td><td>{s['unauthorized_writes']}</td></tr>"
        for label, s in summarize(attempts).items())
    cards = []
    for a in attempts:
        status = "PASS" if a["passed"] else "FAIL"
        before = [p for p in a["before"] if p["operation"] == "select"]
        after = [p for p in a["after"] if p["operation"] == "select"]
        rows = "".join(
            f"<tr><td>{escape(p['schema'])}.{escape(p['table'])}</td><td>{escape(p['actor'])}</td>"
            f"<td>{escape(str(p['ids']))} {escape(str(p['sqlstate'] or ''))}</td>"
            f"<td>{escape(str(q['ids']))} {escape(str(q['sqlstate'] or ''))}</td></tr>"
            for p, q in zip(before, after, strict=True))
        cards.append(f"""<details><summary class='{status.lower()}'>{status} — {escape(a['control'])} /
          {escape(a['task'])} / run {a['run']} — leaked rows: {a['unauthorized_reads']}</summary>
          <h3>Candidate SQL (deterministic control)</h3>{code(a['candidate_sql'])}
          <h3>Independent access checks</h3><div class='scroll'><table><thead><tr><th>Table</th><th>Actor</th><th>Before IDs / SQLSTATE</th><th>After IDs / SQLSTATE</th></tr></thead><tbody>{rows}</tbody></table></div>
          <h3>Hard gates</h3>{code(a['checks'])}<h3>Leaked synthetic fixture rows</h3>{code(a['leaks'])}
          <h3>Full rollback-only operation evidence</h3>{code(a['after'])}</details>""")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
      <title>RLS TwinGuard — repair without permission expansion</title><style>
      :root {{color-scheme:light; font:16px/1.55 system-ui,sans-serif; background:#f5f7f9;color:#172b3a}}
      body {{max-width:1120px;margin:3rem auto;padding:0 1.3rem}} h1 {{font-size:2.5rem;line-height:1.1;letter-spacing:-.06em}}
      h2 {{margin-top:2.5rem}} .label {{font-weight:650;color:#40556a}} .warning {{border-left:4px solid #bc6417;padding:1rem;background:#fff5e9}}
      table {{width:100%;border-collapse:collapse;background:white;text-align:left}} th,td {{padding:.8rem;border-bottom:1px solid #d8e0e6}}
      details {{background:white;border:1px solid #d8e0e6;margin:1rem 0;padding:1rem;border-radius:6px}} summary {{cursor:pointer;font-weight:650}}
      .fail {{color:#9c2030}} .pass {{color:#12603e}} pre {{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef2f5;padding:1rem;font:13px/1.5 ui-monospace,monospace}}
      .scroll {{overflow-x:auto}} @media(max-width:600px) {{body {{margin:1.5rem auto}}h1 {{font-size:2rem}}th,td {{padding:.4rem}}}}
      </style><main><p class='label'>SUPABASE EVALS SCENARIO PACK / LOCAL POSTGRESQL</p>
      <h1>The app works.<br>Did the repair open another tenant's data?</h1>
      <p>RLS TwinGuard compares the happy path with independent permission checks.</p>
      <p class='warning'>Real PostgreSQL RLS and SQL clients. Synthetic users and claims. Deterministic candidate controls, not LLM performance. No hosted Supabase, Auth, PostgREST or MCP execution.</p>
      <h2>Outcomes are not averaged</h2><div class='scroll'><table><thead><tr><th>Control</th><th>Safe passes</th><th>Happy path</th><th>Unauthorized read observations</th><th>Unauthorized write observations</th></tr></thead><tbody>{summary_rows}</tbody></table></div>
      <p>Read observations count unexpected row IDs per identity/table/attempt, not distinct customer records. Repeats test reproducibility; they are not independent statistical samples.</p>
      <h2>Inspect a paired attempt</h2><p>Actors 0 and 1 are separate tenant users; anon has no identity. Open an unsafe attempt to see the exact leaked synthetic rows.</p>{''.join(cards)}</main></html>"""
