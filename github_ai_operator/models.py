from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class RepoProfile:
    full_name: str
    html_url: str
    clone_url: str
    description: str = ''
    language: Optional[str] = None
    stars: int = 0
    topics: List[str] = field(default_factory=list)
    default_branch: Optional[str] = None
    archived: bool = False
    disabled: bool = False
    fork: bool = False
    open_issues_count: int = 0
    owner_login: Optional[str] = None
    homepage: Optional[str] = None
    pushed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewResult:
    summary: str
    praise: List[str]
    concerns: List[str]
    improvements: List[str]
    issue_title: str
    issue_body: str
    confidence: float


@dataclass
class Contact:
    company_id: str
    company_name: str
    category: str
    product: str
    handles: List[str]


@dataclass
class EcosystemMatch:
    company_id: str
    company_name: str
    confidence: float
    reasons: List[str]
    matched_terms: List[str] = field(default_factory=list)


@dataclass
class MaintainerNode:
    login: str
    source: str
    score: float
    x_handle: Optional[str] = None
    company_affinities: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class RankedScores:
    review_score: float
    social_score: float
    relationship_score: float
    ignore_score: float
    quality_score: float
    confidence: float
    niche_affinity: float = 0.0
    freshness_score: float = 0.0
    reasons: List[str] = field(default_factory=list)


@dataclass
class PlannedAction:
    action: str
    reasons: List[str]
    intent: str
    recommended_contacts: Dict[str, List[str]] = field(default_factory=dict)
    recommended_people: List[str] = field(default_factory=list)
    strategy_profile: str = 'balanced'
    operator_notes: List[str] = field(default_factory=list)


@dataclass
class RepoAssessment:
    repo: RepoProfile
    similarity_score: float
    snapshot: Dict[str, Any]
    heuristics: List[str]
    review: ReviewResult
    contribution_rules: Dict[str, Any]
    signals: Dict[str, Any] = field(default_factory=dict)
    ecosystem_matches: List[EcosystemMatch] = field(default_factory=list)
    maintainer_graph: List[MaintainerNode] = field(default_factory=list)
    rank: Optional[RankedScores] = None
    plan: Optional[PlannedAction] = None
