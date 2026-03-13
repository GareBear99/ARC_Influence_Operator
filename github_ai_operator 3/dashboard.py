from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Dict, List


def _esc(value: object) -> str:
    return html.escape(str(value))


def write_dashboard(output_dir: str | Path, title: str, report_index: List[Dict], summary: Dict, write_csv: bool = True) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if write_csv:
        csv_path = output_path / 'repo_index.csv'
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['repo', 'score', 'planned_action', 'posting_result', 'review_score', 'social_score', 'relationship_score', 'ignore_score', 'niche_affinity', 'freshness_score', 'top_ecosystem'])
            for item in report_index:
                rank = item.get('rank') or {}
                ecosystems = item.get('ecosystems') or []
                writer.writerow([
                    item.get('repo', ''),
                    item.get('score', ''),
                    item.get('planned_action', ''),
                    item.get('posting_result', ''),
                    rank.get('review_score', ''),
                    rank.get('social_score', ''),
                    rank.get('relationship_score', ''),
                    rank.get('ignore_score', ''),
                    rank.get('niche_affinity', ''),
                    rank.get('freshness_score', ''),
                    (ecosystems[0].get('company_name', '') if ecosystems else ''),
                ])

    cards = []
    for item in report_index:
        rank = item.get('rank') or {}
        ecosystems = item.get('ecosystems') or []
        maintainers = item.get('maintainers') or []
        people = item.get('recommended_people') or []
        cards.append(f"""
        <article class="card">
          <div class="row"><h3>{_esc(item.get('repo',''))}</h3><span class="pill">{_esc(item.get('planned_action','catalog_only'))}</span></div>
          <p class="meta">score={_esc(item.get('score',''))} · posting={_esc(item.get('posting_result',''))}</p>
          <p><strong>Top ecosystem:</strong> {_esc(ecosystems[0].get('company_name','None') if ecosystems else 'None')}</p>
          <p><strong>Recommended people:</strong> {_esc(', '.join(people) if people else 'None')}</p>
          <p><strong>Top maintainers:</strong> {_esc(', '.join(m.get('login','') for m in maintainers[:4]) if maintainers else 'None')}</p>
          <p><strong>Rank:</strong> review={_esc(rank.get('review_score','-'))} social={_esc(rank.get('social_score','-'))} relationship={_esc(rank.get('relationship_score','-'))} ignore={_esc(rank.get('ignore_score','-'))} niche={_esc(rank.get('niche_affinity','-'))}</p>
        </article>
        """)

    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
body{{font-family:Inter,Arial,sans-serif;background:#0f0f16;color:#f4f1ff;margin:0;padding:24px}}
.wrap{{max-width:1200px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
.card{{background:#1a1625;border:1px solid #33284b;border-radius:18px;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.25)}}
.row{{display:flex;justify-content:space-between;gap:10px;align-items:center}}
.pill{{background:#6d48b3;color:white;border-radius:999px;padding:6px 10px;font-size:12px}}
.meta{{opacity:.8;font-size:14px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:18px 0 22px}}
.stat{{background:#161220;border:1px solid #302547;border-radius:16px;padding:14px}}
h1,h2,h3{{margin:.1em 0 .5em}}
a{{color:#d6b8ff}}
code{{background:#140f1e;padding:2px 6px;border-radius:6px}}
</style>
</head>
<body>
<div class="wrap">
<h1>{_esc(title)}</h1>
<p>Static run dashboard for the latest ARC Influence Operator pass.</p>
<section class="stats">
  <div class="stat"><h3>Processed</h3><div>{_esc(summary.get('processed',0))}</div></div>
  <div class="stat"><h3>Posted</h3><div>{_esc(summary.get('posted',0))}</div></div>
  <div class="stat"><h3>Draft Issues</h3><div>{_esc(summary.get('actions',{}).get('draft_issue',0))}</div></div>
  <div class="stat"><h3>Social Packets</h3><div>{_esc(summary.get('actions',{}).get('prepare_social_packet',0))}</div></div>
  <div class="stat"><h3>Watchlist</h3><div>{_esc(summary.get('actions',{}).get('watchlist',0))}</div></div>
  <div class="stat"><h3>Top Ecosystem</h3><div>{_esc((summary.get('top_ecosystems') or ['None'])[0])}</div></div>
</section>
<h2>Repository cards</h2>
<div class="grid">{''.join(cards)}</div>
<p style="margin-top:24px;opacity:.8">Also written: <code>index.json</code>, <code>run_summary.json</code>, and optionally <code>repo_index.csv</code>.</p>
</div>
</body>
</html>
"""
    (output_path / 'dashboard.html').write_text(html_text, encoding='utf-8')
