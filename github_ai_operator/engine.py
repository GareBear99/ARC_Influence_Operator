from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .action_planner import ActionPlanner
from .ai_client import AIReviewer
from .config import AppConfig
from .contact_directory import ContactDirectory
from .delay import HumanPacer
from .ecosystem_matcher import EcosystemMatcher
from .engagement_ranker import EngagementRanker
from .github_api import GitHubClient
from .issue_writer import default_review, review_from_ai_result
from .ledger import OperatorLedger
from .maintainer_graph import MaintainerGraphBuilder
from .models import PlannedAction, RepoAssessment, RepoProfile
from .repo_signal_extractor import extract_repo_signals
from .review import clone_repo, collect_snapshot, heuristic_findings, read_text, safe_delete
from .similarity import build_queries, cosine_similarity, profile_keywords
from .social_packet import build_social_packet_md
from .dashboard import write_dashboard
from .publisher import PublisherManager
from .source_registry import write_source_registry


class OperatorEngine:
    def __init__(self, cfg: AppConfig, gh: GitHubClient, pacer: HumanPacer) -> None:
        self.cfg = cfg
        self.gh = gh
        self.pacer = pacer
        self.ai = AIReviewer(cfg.ai)
        self.output_dir = Path(cfg.output_dir)
        self.workspace_dir = Path(cfg.workspace_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.daily_state_path = self.output_dir / 'daily_state.json'
        self.daily_state = self._load_daily_state()
        self.ledger = OperatorLedger(self.output_dir / 'ledger.json')
        self.directory = ContactDirectory(cfg.directory.data_dir) if cfg.directory.enabled else None
        self.matcher = EcosystemMatcher(self.directory) if self.directory else None
        self.ranker = EngagementRanker(cfg.niches.weights if cfg.niches.enabled else None)
        self.planner = ActionPlanner(self.directory) if self.directory else None
        self.graph_builder = MaintainerGraphBuilder(self.directory)
        self.publisher = PublisherManager(cfg.distribution, self.output_dir, pacer) if cfg.distribution.enabled else None

    def _load_daily_state(self) -> Dict:
        today = datetime.now(timezone.utc).date().isoformat()
        if self.daily_state_path.exists():
            obj = json.loads(self.daily_state_path.read_text(encoding='utf-8'))
            if obj.get('date') == today:
                return obj
        return {'date': today, 'issues_posted': 0}

    def _save_daily_state(self) -> None:
        self.daily_state_path.write_text(json.dumps(self.daily_state, indent=2), encoding='utf-8')

    def _seed_profiles(self) -> List[tuple[RepoProfile, str]]:
        out = []
        for seed in self.cfg.seed_repos:
            repo = self.gh.get_repo(seed.full_name)
            readme = self.gh.get_readme(seed.full_name)
            out.append((repo, readme))
        return out

    def print_queries(self) -> List[str]:
        seeds = self._seed_profiles()
        queries = build_queries(seeds, self.cfg.search.custom_queries, self.cfg.search.min_stars, self.cfg.search.pushed_after)
        for q in queries:
            print(q)
        return queries

    def run(self) -> None:
        seeds = self._seed_profiles()
        queries = build_queries(seeds, self.cfg.search.custom_queries, self.cfg.search.min_stars, self.cfg.search.pushed_after)
        seed_keywords: List[str] = []
        for repo, readme in seeds:
            seed_keywords.extend(profile_keywords(repo, readme))

        seen = set(seed.full_name for seed in self.cfg.seed_repos)
        processed = 0
        posted = 0
        report_index: List[Dict] = []

        for query in queries:
            if processed >= self.cfg.limits.max_repos_per_run:
                break
            self.pacer.before_search()
            for repo in self.gh.search_repositories(query, per_page=min(10, self.cfg.limits.max_repos_per_run)):
                if processed >= self.cfg.limits.max_repos_per_run:
                    break
                if repo.full_name in seen:
                    continue
                seen.add(repo.full_name)
                if repo.archived and not self.cfg.search.include_archived:
                    continue
                if repo.fork and not self.cfg.search.include_forks:
                    continue
                if repo.stars < self.cfg.search.min_stars:
                    continue
                if self.cfg.search.languages and (repo.language or '').lower() not in {x.lower() for x in self.cfg.search.languages}:
                    continue
                if self.cfg.search.required_topics:
                    topics = {t.lower() for t in repo.topics}
                    if not topics.intersection({x.lower() for x in self.cfg.search.required_topics}):
                        continue

                assessment = self._assess_repo(repo, seed_keywords)
                if assessment.similarity_score < self.cfg.limits.min_similarity_score:
                    continue
                assessment = self._apply_cooldowns(assessment)
                action = self._handle_posting(assessment)
                report_index.append({
                    'repo': repo.full_name,
                    'score': assessment.similarity_score,
                    'planned_action': assessment.plan.action if assessment.plan else 'catalog_only',
                    'posting_result': action,
                    'ecosystems': [asdict(x) for x in assessment.ecosystem_matches],
                    'maintainers': [asdict(x) for x in assessment.maintainer_graph[:6]],
                    'rank': asdict(assessment.rank) if assessment.rank else None,
                    'recommended_people': assessment.plan.recommended_people if assessment.plan else [],
                })
                self.ledger.record(repo.full_name, {
                    'action': assessment.plan.action if assessment.plan else 'catalog_only',
                    'posting_result': action,
                    'recommended_contacts': assessment.plan.recommended_contacts if assessment.plan else {},
                    'ecosystems': [asdict(x) for x in assessment.ecosystem_matches],
                    'maintainers': [asdict(x) for x in assessment.maintainer_graph[:6]],
                    'similarity_score': assessment.similarity_score,
                })
                processed += 1
                if action == 'posted':
                    posted += 1

        self._save_daily_state()
        self.ledger.save()
        (self.output_dir / 'index.json').write_text(json.dumps(report_index, indent=2), encoding='utf-8')
        summary = self._build_run_summary(report_index, processed, posted)
        (self.output_dir / 'run_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        if self.cfg.dashboard.enabled:
            write_dashboard(self.output_dir, self.cfg.dashboard.title, report_index, summary, write_csv=self.cfg.dashboard.write_csv)
        if self.publisher and self.cfg.distribution.enabled and self.cfg.distribution.stage_packets:
            self.publisher._refresh_queue_index()
        write_source_registry(self.output_dir)
        print(f'[done] processed={processed} posted={posted} output={self.output_dir}')


    def _build_run_summary(self, report_index: List[Dict], processed: int, posted: int) -> Dict:
        actions: Dict[str, int] = {}
        ecosystems: Dict[str, int] = {}
        for item in report_index:
            action = item.get('planned_action', 'catalog_only')
            actions[action] = actions.get(action, 0) + 1
            for eco in item.get('ecosystems', [])[:3]:
                name = eco.get('company_name') or eco.get('company_id') or 'Unknown'
                ecosystems[name] = ecosystems.get(name, 0) + 1
        top_ecosystems = [name for name, _ in sorted(ecosystems.items(), key=lambda kv: (-kv[1], kv[0]))[:8]]
        return {
            'processed': processed,
            'posted': posted,
            'actions': actions,
            'top_ecosystems': top_ecosystems,
            'strategy_profile': self.cfg.strategy.profile,
            'generated_at': datetime.now(timezone.utc).isoformat(),
        }

    def _apply_cooldowns(self, assessment: RepoAssessment) -> RepoAssessment:
        plan = assessment.plan
        if not plan:
            return assessment
        contacts = self.ledger.filter_contacts_by_cooldown(
            assessment.repo.full_name,
            plan.recommended_contacts,
            self.cfg.cooldowns.contact_days,
        )
        reasons = list(plan.reasons)
        action = plan.action
        if self.ledger.repo_in_cooldown(assessment.repo.full_name, self.cfg.cooldowns.repo_days):
            reasons.insert(0, f'Repo is still inside the {self.cfg.cooldowns.repo_days}-day cooldown window.')
            if action in {'draft_issue', 'prepare_social_packet'}:
                action = 'watchlist'
        if plan.recommended_contacts and not contacts and action in {'prepare_social_packet', 'watchlist'}:
            reasons.insert(0, 'All suggested contacts are currently in cooldown; keeping this as catalog/watchlist only.')
            action = 'catalog_only'
        return replace(assessment, plan=PlannedAction(
            action=action,
            reasons=reasons[:8],
            intent=plan.intent,
            recommended_contacts=contacts,
            recommended_people=plan.recommended_people,
            strategy_profile=plan.strategy_profile,
            operator_notes=plan.operator_notes,
        ))

    def _assess_repo(self, repo: RepoProfile, seed_keywords: List[str]) -> RepoAssessment:
        self.pacer.before_clone()
        target_dir = self.workspace_dir / repo.full_name.replace('/', '__')
        try:
            if not clone_repo(repo.clone_url, target_dir, depth=self.cfg.limits.max_clone_depth):
                raise RuntimeError(f'clone failed for {repo.full_name}')
            snapshot = collect_snapshot(target_dir, self.cfg.limits)
            heuristics = heuristic_findings(target_dir, snapshot)
            repo_keywords = profile_keywords(repo, '')
            score = cosine_similarity(seed_keywords, repo_keywords)
            contribution_rules = self.gh.get_contributing_rules(repo.full_name)
            readme = read_text(target_dir / 'README.md', 20000) or read_text(target_dir / 'readme.md', 20000)
            signals = extract_repo_signals(repo, readme, target_dir, snapshot)
            ecosystem_matches = self.matcher.match(repo, readme, signals) if self.matcher else []
            contributors = self.gh.get_top_contributors(repo.full_name, per_page=self.cfg.limits.max_contributors)
            issue_users = self.gh.get_issue_participants(repo.full_name, per_page=self.cfg.limits.max_issue_participants)
            maintainer_graph = self.graph_builder.build(repo, contributors, issue_users, readme or '', ecosystem_matches)
            rank = self.ranker.score(repo, score, heuristics, ecosystem_matches, contribution_rules, signals)
            plan = self.planner.plan(repo, rank, ecosystem_matches, contribution_rules, heuristics, maintainers=maintainer_graph, strategy_profile=self.cfg.strategy.profile, max_human_targets=self.cfg.strategy.max_human_targets) if self.planner else None
            review = self._build_review(repo, score, snapshot, heuristics, contribution_rules, ecosystem_matches, maintainer_graph, rank, plan)
            assessment = RepoAssessment(
                repo=repo,
                similarity_score=score,
                snapshot={k: v for k, v in snapshot.items() if k != 'source_samples'},
                heuristics=heuristics,
                review=review,
                contribution_rules=contribution_rules,
                signals=signals,
                ecosystem_matches=ecosystem_matches,
                maintainer_graph=maintainer_graph,
                rank=rank,
                plan=plan,
            )
            self._save_assessment(assessment)
            if self.publisher:
                self.publisher.stage_assessment(assessment)
            return assessment
        finally:
            safe_delete(target_dir)

    def _build_review(self, repo: RepoProfile, score: float, snapshot: Dict, heuristics: List[str], contribution_rules: Dict, ecosystem_matches, maintainer_graph, rank, plan):
        payload = {
            'repo': repo.to_dict(),
            'similarity_score': score,
            'snapshot': {k: v for k, v in snapshot.items() if k != 'source_samples'},
            'heuristics': heuristics,
            'contribution_rules': contribution_rules,
            'ecosystem_matches': [asdict(x) for x in ecosystem_matches],
            'maintainer_graph': [asdict(x) for x in maintainer_graph],
            'rank': asdict(rank) if rank else None,
            'plan': asdict(plan) if plan else None,
            'task': 'Return JSON with keys summary, praise, concerns, improvements, issue_title, issue_body, confidence. Be constructive and avoid overstating uncertainty.',
        }
        ai_result = None
        try:
            ai_result = self.ai.review(payload)
        except Exception as e:
            print(f'[ai-fallback] {e}')
        if ai_result:
            return review_from_ai_result(repo, ai_result)
        return default_review(repo, score, heuristics)

    def _save_assessment(self, assessment: RepoAssessment) -> None:
        slug = assessment.repo.full_name.replace('/', '__')
        report = {
            'repo': assessment.repo.to_dict(),
            'similarity_score': assessment.similarity_score,
            'snapshot': assessment.snapshot,
            'heuristics': assessment.heuristics,
            'review': asdict(assessment.review),
            'contribution_rules': assessment.contribution_rules,
            'signals': assessment.signals,
            'ecosystem_matches': [asdict(x) for x in assessment.ecosystem_matches],
            'maintainer_graph': [asdict(x) for x in assessment.maintainer_graph],
            'rank': asdict(assessment.rank) if assessment.rank else None,
            'plan': asdict(assessment.plan) if assessment.plan else None,
        }
        (self.output_dir / f'{slug}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        md = [
            f'# {assessment.repo.full_name}',
            '',
            f'URL: {assessment.repo.html_url}',
            '',
            f'Similarity score: {assessment.similarity_score:.3f}',
            '',
            '## Summary',
            assessment.review.summary,
            '',
            '## Planned Action',
            assessment.plan.action if assessment.plan else 'catalog_only',
            '',
            '## Plan Reasons',
            *[f'- {x}' for x in ((assessment.plan.reasons if assessment.plan else []) or ['No plan reasons available.'])],
            '',
            '## Ecosystem Matches',
            *([f"- {m.company_name} ({m.confidence:.2f}): {'; '.join(m.reasons)}" for m in assessment.ecosystem_matches] or ['- None']),
            '',
            '## Suggested Contacts',
            *([f"- {company}: {', '.join(handles)}" for company, handles in ((assessment.plan.recommended_contacts if assessment.plan else {}) or {}).items()] or ['- None']),
            '',
            '## Recommended People',
            *([f'- {x}' for x in ((assessment.plan.recommended_people if assessment.plan else []) or ['None'])]),
            '',
            '## Operator Notes',
            *([f'- {x}' for x in ((assessment.plan.operator_notes if assessment.plan else []) or ['None'])]),
            '',
            '## Maintainer Graph',
            *([f"- {m.login} | source={m.source} | score={m.score:.3f} | x={(m.x_handle or '-')} | companies={(', '.join(m.company_affinities) if m.company_affinities else '-')}" for m in assessment.maintainer_graph] or ['- None']),
            '',
            '## Rank Scores',
            *([f'- review={assessment.rank.review_score:.3f} social={assessment.rank.social_score:.3f} relationship={assessment.rank.relationship_score:.3f} ignore={assessment.rank.ignore_score:.3f} niche={assessment.rank.niche_affinity:.3f} freshness={assessment.rank.freshness_score:.3f} confidence={assessment.rank.confidence:.3f}'] if assessment.rank else ['- None']),
            '',
            '## Praise',
            *[f'- {x}' for x in assessment.review.praise],
            '',
            '## Concerns',
            *[f'- {x}' for x in assessment.review.concerns],
            '',
            '## Improvements',
            *[f'- {x}' for x in assessment.review.improvements],
            '',
            '## Suggested Issue Title',
            assessment.review.issue_title,
            '',
            '## Suggested Issue Body',
            assessment.review.issue_body,
            '',
            '## Contribution Files Found',
            *[f'- {x}' for x in assessment.contribution_rules.get('files', [])],
        ]
        (self.output_dir / f'{slug}.md').write_text('\n'.join(md), encoding='utf-8')

        if self.cfg.directory.write_social_packets:
            (self.output_dir / f'{slug}.social.md').write_text(build_social_packet_md(assessment), encoding='utf-8')
        if self.cfg.directory.write_company_summaries and self.directory:
            company_dir = self.output_dir / 'companies'
            company_dir.mkdir(parents=True, exist_ok=True)
            for match in assessment.ecosystem_matches[:3]:
                (company_dir / f'{match.company_id}.json').write_text(json.dumps(self.directory.to_summary(match.company_id), indent=2), encoding='utf-8')

    def _handle_posting(self, assessment: RepoAssessment) -> str:
        posting = self.cfg.posting
        repo_name = assessment.repo.full_name
        if repo_name in posting.denylist:
            return 'denied'
        if assessment.plan and assessment.plan.action != 'draft_issue':
            return assessment.plan.action
        if posting.skip_if_contributing_missing and not assessment.contribution_rules.get('files'):
            return 'skipped_no_contrib_rules'
        if assessment.review.confidence < self.cfg.limits.min_issue_confidence:
            return 'low_confidence'

        title_key = assessment.review.issue_title.lower().strip()
        issues = self.gh.list_issues(repo_name)
        for issue in issues:
            if 'pull_request' in issue:
                continue
            existing_title = str(issue.get('title', '')).lower()
            if title_key == existing_title or title_key in existing_title or existing_title in title_key:
                return 'duplicate_title'

        if posting.draft_only or not posting.enabled:
            return 'draft_only'
        if posting.require_manual_approval:
            return 'manual_approval_required'
        if posting.allowlist and repo_name not in posting.allowlist:
            return 'not_allowlisted'
        if self.daily_state['issues_posted'] >= self.cfg.limits.max_issue_posts_per_day:
            return 'daily_limit_reached'
        if self.daily_state['issues_posted'] >= self.cfg.limits.max_issue_posts_per_run:
            return 'run_limit_reached'

        self.pacer.before_issue()
        self.gh.create_issue(repo_name, assessment.review.issue_title, assessment.review.issue_body, labels=posting.labels)
        self.daily_state['issues_posted'] += 1
        return 'posted'


    def publish_pending(self) -> List[Dict]:
        if not self.publisher:
            return []
        return self.publisher.publish_pending()
