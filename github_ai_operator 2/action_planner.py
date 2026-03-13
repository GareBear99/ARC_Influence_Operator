from __future__ import annotations

from typing import Dict, List

from .contact_directory import ContactDirectory
from .models import EcosystemMatch, MaintainerNode, PlannedAction, RankedScores, RepoProfile
from .strategy import blend_people, build_operator_notes


class ActionPlanner:
    def __init__(self, directory: ContactDirectory) -> None:
        self.directory = directory

    def plan(
        self,
        repo: RepoProfile,
        rank: RankedScores,
        ecosystem_matches: List[EcosystemMatch],
        contribution_rules: Dict,
        heuristics: List[str],
        maintainers: List[MaintainerNode] | None = None,
        strategy_profile: str = 'balanced',
        max_human_targets: int = 8,
    ) -> PlannedAction:
        reasons: List[str] = []
        recommended_contacts: Dict[str, List[str]] = {}
        maintainers = maintainers or []

        if rank.ignore_score >= 0.55:
            return PlannedAction(action='ignore', reasons=rank.reasons[:4], intent='none', recommended_contacts={}, recommended_people=[], strategy_profile=strategy_profile, operator_notes=build_operator_notes(strategy_profile, repo, rank, ecosystem_matches, maintainers))

        top_match = ecosystem_matches[0] if ecosystem_matches else None
        if rank.review_score >= 0.45 and contribution_rules.get('files'):
            intent = 'technical_help'
            action = 'draft_issue'
            reasons.append('Repo appears review-worthy and has contribution guidance.')
        elif rank.social_score >= 0.42 and top_match:
            intent = 'showcase_build'
            action = 'prepare_social_packet'
            reasons.append('Strong enough ecosystem alignment for non-spammy social prep.')
        elif rank.relationship_score >= 0.35 and top_match:
            intent = 'relationship_build'
            action = 'watchlist'
            reasons.append('Worth tracking for future relationship building.')
        else:
            intent = 'community_visibility' if top_match else 'none'
            action = 'catalog_only'
            reasons.append('Signals are useful, but not strong enough for active outreach.')

        for match in ecosystem_matches[:3]:
            recommended_contacts[match.company_id] = self.directory.get_best_contacts(match.company_id, intent)

        if len(heuristics) > 4:
            reasons.append('Higher heuristic count suggests keeping actions conservative.')
        if not ecosystem_matches:
            reasons.append('No directory ecosystem match was found, so contact recommendations are limited.')

        flat_contacts: List[str] = []
        for handles in recommended_contacts.values():
            for handle in handles:
                if handle not in flat_contacts:
                    flat_contacts.append(handle)
        recommended_people = blend_people(strategy_profile, maintainers, flat_contacts, max_people=max_human_targets)
        operator_notes = build_operator_notes(strategy_profile, repo, rank, ecosystem_matches, maintainers)

        return PlannedAction(
            action=action,
            reasons=reasons[:6],
            intent=intent,
            recommended_contacts=recommended_contacts,
            recommended_people=recommended_people,
            strategy_profile=strategy_profile,
            operator_notes=operator_notes,
        )
