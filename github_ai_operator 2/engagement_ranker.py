from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from .models import EcosystemMatch, RankedScores, RepoProfile

NICHE_RULES: Dict[str, List[str]] = {
    'audio_plugin': ['vst', 'vst3', 'au', 'juce', 'synth', 'audio plugin', 'dsp', 'oscillator'],
    'juce_dsp': ['juce', 'dsp', 'pluginprocessor', 'plugineditor', 'audioprocessorvalue'],
    'indie_game': ['godot', 'unity', 'unreal', 'game', 'roguelike', 'steam', 'pixel', 'co-op'],
    'ai_infra': ['llm', 'agent', 'inference', 'embedding', 'vector', 'supabase', 'openrouter', 'groq'],
    'creative_coding': ['shader', 'visualizer', 'processing', 'p5', 'creative coding', 'generative'],
}


def _days_since(iso_ts: str | None) -> int | None:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        return None


class EngagementRanker:
    def __init__(self, niche_weights: Dict[str, float] | None = None) -> None:
        self.niche_weights = niche_weights or {k: 1.0 for k in NICHE_RULES}

    def _niche_affinity(self, repo: RepoProfile, signals: Dict, heuristics: List[str]) -> tuple[float, List[str]]:
        text = ' '.join([
            repo.full_name,
            repo.description or '',
            repo.language or '',
            ' '.join(repo.topics),
            ' '.join(signals.get('terms', [])[:200]),
            ' '.join(signals.get('dependencies', [])[:120]),
            ' '.join(signals.get('frameworks', [])),
            ' '.join(signals.get('infra', [])),
        ]).lower()
        total_weight = max(0.001, sum(float(v) for v in self.niche_weights.values()))
        score = 0.0
        reasons: List[str] = []
        for niche, needles in NICHE_RULES.items():
            if any(n in text for n in needles):
                weight = float(self.niche_weights.get(niche, 0.0))
                if weight > 0:
                    score += weight
                    reasons.append(f'Matches niche profile: {niche}.')
        raw = min(1.0, score / total_weight)
        if len(heuristics) <= 2:
            raw = min(1.0, raw + 0.05)
        return round(raw, 3), reasons[:5]

    def score(self, repo: RepoProfile, similarity_score: float, heuristics: List[str], ecosystem_matches: List[EcosystemMatch], contribution_rules: dict, signals: Dict | None = None) -> RankedScores:
        signals = signals or {}
        reasons: List[str] = []
        review = min(1.0, similarity_score * 0.70)
        social = min(1.0, (similarity_score * 0.35) + (0.08 * len(ecosystem_matches)))
        relationship = min(1.0, (0.12 * len(ecosystem_matches)) + (0.08 if repo.stars >= 5 else 0.0))
        ignore = 0.0
        quality = 0.52

        niche_affinity, niche_reasons = self._niche_affinity(repo, signals, heuristics)
        reasons.extend(niche_reasons)
        review += niche_affinity * 0.22
        social += niche_affinity * 0.18
        relationship += niche_affinity * 0.20

        days = _days_since(repo.pushed_at)
        freshness = 0.5
        if days is not None:
            if days <= 30:
                freshness = 1.0
                social += 0.08
                relationship += 0.05
                reasons.append('Recent repo activity improves outreach timing.')
            elif days <= 120:
                freshness = 0.72
            elif days <= 365:
                freshness = 0.45
                review -= 0.04
            else:
                freshness = 0.18
                ignore += 0.12
                reasons.append('Repo looks stale; keep action conservative.')

        if repo.archived or repo.disabled:
            ignore += 0.45
            reasons.append('Archived or disabled repositories are not ideal engagement targets.')
        if repo.fork:
            ignore += 0.12
            reasons.append('Forks are usually weaker primary engagement targets.')
        if repo.stars >= 25:
            social += 0.12
            relationship += 0.08
            reasons.append('Star count suggests some community traction.')
        elif repo.stars == 0:
            ignore += 0.10
            reasons.append('Zero-star repositories often produce weak public engagement value.')
        if contribution_rules.get('files'):
            review += 0.12
            quality += 0.08
            reasons.append('Contribution guidance exists, which makes constructive issue work safer.')
        else:
            ignore += 0.06
        if len(heuristics) <= 2:
            quality += 0.10
            reasons.append('Low heuristic warning count suggests cleaner repo hygiene.')
        else:
            review += 0.05
            reasons.append('There are enough findings to justify a careful review draft.')
        if ecosystem_matches:
            relationship += 0.10
            social += 0.08
            reasons.append('Matched ecosystem/company signals improve strategic relevance.')
        if similarity_score < 0.25:
            ignore += 0.15
            reasons.append('Similarity is modest; public action should stay conservative.')

        review = min(1.0, max(0.0, review))
        social = min(1.0, max(0.0, social))
        relationship = min(1.0, max(0.0, relationship))
        ignore = min(1.0, max(0.0, ignore))
        quality = min(1.0, max(0.0, quality))
        confidence = max(0.0, min(1.0, (quality + max(review, social, relationship) - ignore) / 1.5))
        return RankedScores(
            review_score=round(review, 3),
            social_score=round(social, 3),
            relationship_score=round(relationship, 3),
            ignore_score=round(ignore, 3),
            quality_score=round(quality, 3),
            confidence=round(confidence, 3),
            niche_affinity=round(niche_affinity, 3),
            freshness_score=round(freshness, 3),
            reasons=reasons[:10],
        )
