from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from .models import RepoProfile

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
HANDLE_RE = re.compile(r'@([A-Za-z0-9_]{2,30})')

KNOWN_FILES = {
    'package.json', 'requirements.txt', 'pyproject.toml', 'poetry.lock', 'Cargo.toml',
    'go.mod', 'composer.json', 'Gemfile', 'Dockerfile', 'wrangler.toml', 'wrangler.jsonc',
    'vercel.json', 'netlify.toml', 'supabase/config.toml', 'drizzle.config.ts', 'drizzle.config.js',
}


def _safe_json(text: str) -> Dict:
    try:
        return json.loads(text)
    except Exception:
        return {}


def _append_unique(items: List[str], value: str) -> None:
    value = value.strip()
    if value and value not in items:
        items.append(value)


def extract_repo_signals(repo: RepoProfile, readme: str, repo_dir: Path, snapshot: Dict) -> Dict:
    terms: List[str] = []
    dependencies: List[str] = []
    frameworks: List[str] = []
    infra: List[str] = []
    links: List[str] = []
    x_handles: List[str] = []
    file_signals: List[str] = []

    for token in repo.topics:
        _append_unique(terms, token.lower())
    if repo.language:
        _append_unique(terms, repo.language.lower())
    for token in re.findall(r'[A-Za-z0-9_./@+-]{3,}', f"{repo.full_name} {repo.description} {readme[:12000]}"):
        t = token.lower()
        if len(t) >= 3:
            _append_unique(terms, t)

    for url in URL_RE.findall(readme[:20000]):
        _append_unique(links, url)

    for h in HANDLE_RE.findall(readme[:15000]):
        _append_unique(x_handles, '@' + h)

    root_files = snapshot.get('root_files', [])
    sources = snapshot.get('source_samples', {})

    interesting = set(root_files) | {p for p in sources if Path(p).name in KNOWN_FILES}
    for rel in sorted(interesting):
        name = Path(rel).name
        if name not in KNOWN_FILES:
            continue
        _append_unique(file_signals, rel)
        text = sources.get(rel, '')
        if name == 'package.json' and text:
            obj = _safe_json(text)
            for bucket in ('dependencies', 'devDependencies', 'peerDependencies'):
                for dep in (obj.get(bucket) or {}).keys():
                    _append_unique(dependencies, dep.lower())
        elif name == 'composer.json' and text:
            obj = _safe_json(text)
            for bucket in ('require', 'require-dev'):
                for dep in (obj.get(bucket) or {}).keys():
                    _append_unique(dependencies, dep.lower())
        else:
            for dep in re.findall(r'[@A-Za-z0-9_.\-/]{3,}', text[:10000]):
                dep_l = dep.lower()
                if any(ch.isalpha() for ch in dep_l) and len(dep_l) > 2:
                    _append_unique(dependencies, dep_l)

    dependency_text = ' '.join(dependencies)
    term_text = ' '.join(terms) + ' ' + dependency_text

    framework_rules = {
        'supabase': ['@supabase/', 'supabase-js', 'supabase'],
        'vercel': ['vercel', 'nextjs', 'next-auth'],
        'cloudflare': ['cloudflare', 'wrangler', 'workers'],
        'laravel': ['laravel'],
        'drizzle': ['drizzle', 'drizzle-orm'],
        'appwrite': ['appwrite'],
        'auth0': ['auth0'],
        'netlify': ['netlify'],
        'better-auth': ['better-auth'],
        'cursor': ['cursor'],
        'groq': ['groq'],
    }
    for label, needles in framework_rules.items():
        if any(n in term_text for n in needles):
            _append_unique(frameworks, label)

    infra_rules = {
        'cloudflare_workers': ['wrangler', 'workers.dev', 'cloudflare'],
        'vercel': ['vercel.json', 'vercel'],
        'netlify': ['netlify.toml', 'netlify'],
        'docker': ['dockerfile', 'docker-compose'],
        'github_actions': ['.github/workflows', 'github actions'],
    }
    lower_files = [x.lower() for x in root_files]
    for label, needles in infra_rules.items():
        hay = ' '.join(lower_files) + ' ' + term_text
        if any(n in hay for n in needles):
            _append_unique(infra, label)

    return {
        'terms': terms[:400],
        'dependencies': dependencies[:400],
        'frameworks': frameworks,
        'infra': infra,
        'links': links[:50],
        'x_handles': x_handles[:25],
        'file_signals': file_signals,
    }
