from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import json


@dataclass
class DelayProfile:
    min_search_seconds: float = 2.0
    max_search_seconds: float = 8.0
    min_clone_seconds: float = 3.0
    max_clone_seconds: float = 12.0
    min_issue_seconds: float = 20.0
    max_issue_seconds: float = 90.0
    jitter_seconds: float = 1.25


@dataclass
class Limits:
    max_repos_per_run: int = 15
    max_issue_posts_per_run: int = 2
    max_issue_posts_per_day: int = 4
    max_clone_depth: int = 1
    max_files_scanned: int = 250
    max_source_chars_per_file: int = 12000
    min_similarity_score: float = 0.18
    min_issue_confidence: float = 0.72
    max_issue_participants: int = 15
    max_contributors: int = 15


@dataclass
class SearchConfig:
    mode: str = 'related'
    custom_queries: List[str] = field(default_factory=list)
    include_forks: bool = False
    include_archived: bool = False
    min_stars: int = 0
    pushed_after: Optional[str] = None
    languages: List[str] = field(default_factory=list)
    required_topics: List[str] = field(default_factory=list)


@dataclass
class PostingConfig:
    enabled: bool = False
    draft_only: bool = True
    require_manual_approval: bool = False
    allowlist: List[str] = field(default_factory=list)
    denylist: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=lambda: ['ai-review'])
    skip_if_contributing_missing: bool = False
    avoid_existing_issue_titles_like: List[str] = field(default_factory=lambda: ['review', 'bug', 'issue', 'feedback'])


@dataclass
class AIConfig:
    enabled: bool = False
    api_url: Optional[str] = None
    api_key_env: str = 'AI_API_KEY'
    model: str = 'gpt-4o-mini'


@dataclass
class DirectoryConfig:
    enabled: bool = True
    data_dir: Optional[str] = None
    write_social_packets: bool = True
    write_company_summaries: bool = True


@dataclass
class CooldownConfig:
    repo_days: int = 14
    contact_days: int = 30
    watchlist_days: int = 7


@dataclass
class NicheConfig:
    enabled: bool = True
    weights: Dict[str, float] = field(default_factory=lambda: {
        'audio_plugin': 1.0,
        'juce_dsp': 1.0,
        'indie_game': 0.9,
        'ai_infra': 0.85,
        'creative_coding': 0.75,
    })




@dataclass
class StrategyConfig:
    profile: str = "balanced"
    blend_directory_with_maintainers: bool = True
    prefer_seed_contacts_for_social: bool = True
    max_human_targets: int = 8


@dataclass
class DashboardConfig:
    enabled: bool = True
    title: str = "ARC Influence Operator"
    default_sort: str = "score"
    write_csv: bool = True



@dataclass
class OutletConfig:
    enabled: bool = False
    mode: str = "draft_only"
    destinations: List[str] = field(default_factory=list)
    api_base: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    title_prefix: str = ""
    max_targets: int = 4


@dataclass
class DistributionConfig:
    enabled: bool = False
    stage_packets: bool = True
    min_social_score: float = 0.55
    max_posts_per_run: int = 3
    reddit: OutletConfig = field(default_factory=OutletConfig)
    bluesky: OutletConfig = field(default_factory=OutletConfig)
    mastodon: OutletConfig = field(default_factory=OutletConfig)
    devto: OutletConfig = field(default_factory=OutletConfig)
    hashnode: OutletConfig = field(default_factory=OutletConfig)
    medium: OutletConfig = field(default_factory=OutletConfig)
    discord: OutletConfig = field(default_factory=OutletConfig)
    matrix: OutletConfig = field(default_factory=OutletConfig)
    nostr: OutletConfig = field(default_factory=OutletConfig)
    rss: OutletConfig = field(default_factory=OutletConfig)
    webhook: OutletConfig = field(default_factory=OutletConfig)


@dataclass
class SeedRepo:
    full_name: str
    weight: float = 1.0


@dataclass
class AppConfig:
    output_dir: str = 'output'
    workspace_dir: str = '.tmp_workspace'
    seed_repos: List[SeedRepo] = field(default_factory=list)
    delay_profile: DelayProfile = field(default_factory=DelayProfile)
    limits: Limits = field(default_factory=Limits)
    search: SearchConfig = field(default_factory=SearchConfig)
    posting: PostingConfig = field(default_factory=PostingConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    directory: DirectoryConfig = field(default_factory=DirectoryConfig)
    cooldowns: CooldownConfig = field(default_factory=CooldownConfig)
    niches: NicheConfig = field(default_factory=NicheConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    distribution: DistributionConfig = field(default_factory=DistributionConfig)

    @staticmethod
    def from_json(path: str | Path) -> 'AppConfig':
        raw = json.loads(Path(path).read_text(encoding='utf-8'))

        def seed_repo(item: dict) -> SeedRepo:
            return SeedRepo(full_name=item['full_name'], weight=float(item.get('weight', 1.0)))

        return AppConfig(
            output_dir=raw.get('output_dir', 'output'),
            workspace_dir=raw.get('workspace_dir', '.tmp_workspace'),
            seed_repos=[seed_repo(x) for x in raw.get('seed_repos', [])],
            delay_profile=DelayProfile(**raw.get('delay_profile', {})),
            limits=Limits(**raw.get('limits', {})),
            search=SearchConfig(**raw.get('search', {})),
            posting=PostingConfig(**raw.get('posting', {})),
            ai=AIConfig(**raw.get('ai', {})),
            directory=DirectoryConfig(**raw.get('directory', {})),
            cooldowns=CooldownConfig(**raw.get('cooldowns', {})),
            niches=NicheConfig(**raw.get('niches', {})),
            strategy=StrategyConfig(**raw.get('strategy', {})),
            dashboard=DashboardConfig(**raw.get('dashboard', {})),
            distribution=DistributionConfig(
                enabled=raw.get('distribution', {}).get('enabled', False),
                stage_packets=raw.get('distribution', {}).get('stage_packets', True),
                min_social_score=raw.get('distribution', {}).get('min_social_score', 0.55),
                max_posts_per_run=raw.get('distribution', {}).get('max_posts_per_run', 3),
                reddit=OutletConfig(**raw.get('distribution', {}).get('reddit', {})),
                bluesky=OutletConfig(**raw.get('distribution', {}).get('bluesky', {})),
                mastodon=OutletConfig(**raw.get('distribution', {}).get('mastodon', {})),
                devto=OutletConfig(**raw.get('distribution', {}).get('devto', {})),
                hashnode=OutletConfig(**raw.get('distribution', {}).get('hashnode', {})),
                medium=OutletConfig(**raw.get('distribution', {}).get('medium', {})),
                discord=OutletConfig(**raw.get('distribution', {}).get('discord', {})),
                matrix=OutletConfig(**raw.get('distribution', {}).get('matrix', {})),
                nostr=OutletConfig(**raw.get('distribution', {}).get('nostr', {})),
                rss=OutletConfig(**raw.get('distribution', {}).get('rss', {})),
                webhook=OutletConfig(**raw.get('distribution', {}).get('webhook', {})),
            ),
        )
