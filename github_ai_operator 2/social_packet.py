from __future__ import annotations

from typing import List

from .models import RepoAssessment


def build_social_packet_md(assessment: RepoAssessment) -> str:
    match_lines: List[str] = []
    for match in assessment.ecosystem_matches[:3]:
        contacts = []
        if assessment.plan:
            contacts = assessment.plan.recommended_contacts.get(match.company_id, [])
        match_lines.append(f"- **{match.company_name}** (confidence {match.confidence:.2f})")
        if match.reasons:
            match_lines.extend([f"  - {reason}" for reason in match.reasons[:3]])
        if contacts:
            match_lines.append(f"  - Suggested handles: {', '.join(contacts)}")

    action = assessment.plan.action if assessment.plan else 'catalog_only'
    intent = assessment.plan.intent if assessment.plan else 'none'
    plan_reasons = assessment.plan.reasons if assessment.plan else []
    rank_reasons = assessment.rank.reasons if assessment.rank else []

    return '\n'.join([
        f"# Social Packet — {assessment.repo.full_name}",
        '',
        f"Repo URL: {assessment.repo.html_url}",
        f"Suggested action: **{action}**",
        f"Intent: **{intent}**",
        '',
        '## Why this repo matters',
        assessment.review.summary,
        '',
        '## Ecosystem matches',
        *(match_lines or ['- No strong company/contact match found in the bundled directory.']),
        '',
        '## Suggested careful outreach angle',
        '- Lead with something concrete you built, fixed, or learned.',
        '- Prefer relevant humans over mass-tagging everybody.',
        '- Avoid asking for amplification directly; show value first.',
        '',
        '## Action rationale',
        *[f'- {x}' for x in (plan_reasons + rank_reasons)[:10]],
        '',
        '## Review highlights',
        *[f'- {x}' for x in assessment.review.improvements[:5]],
    ])
