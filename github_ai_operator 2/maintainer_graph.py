from __future__ import annotations

import re
from typing import Dict, Iterable, List

from .contact_directory import ContactDirectory
from .models import EcosystemMatch, MaintainerNode, RepoProfile

HANDLE_RE = re.compile(r'@([A-Za-z0-9_]{2,30})')


class MaintainerGraphBuilder:
    def __init__(self, directory: ContactDirectory | None = None) -> None:
        self.directory = directory

    def build(
        self,
        repo: RepoProfile,
        contributors: List[Dict],
        issue_users: List[Dict],
        readme: str,
        ecosystem_matches: List[EcosystemMatch],
    ) -> List[MaintainerNode]:
        nodes: Dict[str, MaintainerNode] = {}

        def upsert(login: str, source: str, score: float, reason: str, x_handle: str | None = None, affinities: List[str] | None = None) -> None:
            key = login.lower().strip()
            if not key:
                return
            node = nodes.get(key)
            if node is None:
                node = MaintainerNode(login=login, source=source, score=0.0)
                nodes[key] = node
            node.score += score
            if node.source != source and source not in node.source:
                node.source = f'{node.source}+{source}'
            if x_handle and not node.x_handle:
                node.x_handle = x_handle
            for a in affinities or []:
                if a not in node.company_affinities:
                    node.company_affinities.append(a)
            if reason not in node.reasons:
                node.reasons.append(reason)

        if repo.owner_login:
            upsert(repo.owner_login, 'owner', 1.0, 'Repository owner', affinities=[m.company_id for m in ecosystem_matches[:2]])

        for idx, item in enumerate(contributors[:15]):
            login = str(item.get('login') or '').strip()
            if login:
                contribs = int(item.get('contributions', 0) or 0)
                score = 0.85 - (idx * 0.04) + min(0.25, contribs / 200.0)
                upsert(login, 'contributor', max(0.2, score), f'Top contributor ({contribs} contributions)')

        for idx, item in enumerate(issue_users[:15]):
            login = str(item.get('login') or '').strip()
            if login:
                comments = int(item.get('comments', 0) or 0)
                score = 0.55 - (idx * 0.03) + min(0.2, comments / 50.0)
                upsert(login, 'issue_participant', max(0.1, score), f'Issue/discussion participant ({comments} comments)')

        handles = ['@' + h for h in HANDLE_RE.findall(readme[:20000])]
        for idx, handle in enumerate(handles[:10]):
            login = handle.lstrip('@')
            upsert(login, 'readme_handle', 0.45 - (idx * 0.02), 'X handle found in README', x_handle=handle)

        if self.directory:
            for match in ecosystem_matches[:3]:
                for handle in self.directory.get_best_contacts(match.company_id, 'community_visibility')[:4]:
                    login = handle.lstrip('@')
                    upsert(login, 'seed_directory', 0.35, f'Seed contact for {match.company_name}', x_handle=handle, affinities=[match.company_id])

        ordered = sorted(nodes.values(), key=lambda n: (-n.score, n.login.lower()))
        for node in ordered:
            node.score = round(min(1.0, node.score), 3)
        return ordered[:20]
