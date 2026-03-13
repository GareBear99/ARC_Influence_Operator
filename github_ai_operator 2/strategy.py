from __future__ import annotations

from typing import List

from .models import EcosystemMatch, MaintainerNode, RankedScores, RepoProfile


def build_operator_notes(profile: str, repo: RepoProfile, rank: RankedScores, ecosystem_matches: List[EcosystemMatch], maintainers: List[MaintainerNode]) -> List[str]:
    profile = (profile or 'balanced').lower().strip()
    notes: List[str] = []
    if profile == 'audio_plugin':
        notes.append('Use a builder-to-builder angle: DSP quality, UX polish, and host compatibility matter more than generic hype.')
    elif profile == 'indie_game':
        notes.append('Lead with gameplay/engine specifics rather than vague praise; systems and feel matter most here.')
    elif profile == 'ai_infra':
        notes.append('Keep claims concrete. Infrastructure maintainers respond better to measured technical value than broad vision pitches.')
    else:
        notes.append('Balanced mode: prefer careful technical value first, social amplification second.')

    if ecosystem_matches:
        notes.append(f'Top ecosystem target: {ecosystem_matches[0].company_name}. Keep references relevant to that stack.')
    if maintainers:
        notes.append(f'Prioritize a short human list. Top mapped maintainer: {maintainers[0].login}.')
    if rank.niche_affinity >= 0.6:
        notes.append('Niche affinity is strong enough to justify a tailored operator brief.')
    if rank.freshness_score < 0.3:
        notes.append('Repo looks stale. Treat this as catalog/watchlist unless there is a very clear reason to engage.')
    return notes[:5]


def blend_people(profile: str, maintainers: List[MaintainerNode], contacts: List[str], max_people: int = 8) -> List[str]:
    profile = (profile or 'balanced').lower().strip()
    picked: List[str] = []
    seen = set()

    def add(value: str) -> None:
        key = value.lower().strip()
        if value and key not in seen and len(picked) < max_people:
            seen.add(key)
            picked.append(value)

    prefer_handles_first = profile in {'audio_plugin', 'balanced', 'ai_infra'}
    if prefer_handles_first:
        for h in contacts:
            add(h)

    for node in maintainers[:12]:
        if node.x_handle:
            add(node.x_handle)
        else:
            add(node.login)

    if not prefer_handles_first:
        for h in contacts:
            add(h)

    return picked[:max_people]
