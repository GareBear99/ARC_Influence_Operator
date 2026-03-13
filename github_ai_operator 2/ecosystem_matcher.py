from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .contact_directory import ContactDirectory
from .models import EcosystemMatch, RepoProfile


ALIASES: Dict[str, List[str]] = {
    'appwrite': ['appwrite'],
    'auth0': ['auth0'],
    'autumn': ['autumn'],
    'axiom': ['axiom'],
    'betterauth': ['betterauth', 'better-auth'],
    'cloudflare': ['cloudflare', 'wrangler', 'workers.dev', 'cloudflare workers'],
    'computesdk': ['compute sdk', 'computesdk'],
    'coolify': ['coolify'],
    'cursor': ['cursor'],
    'depot': ['depot'],
    'dodopayments': ['dodo', 'dodo payments', 'dodopayments'],
    'drizzle': ['drizzle', 'drizzle-orm'],
    'dub': ['dub', 'dub.co'],
    'e2b': ['e2b'],
    'google-ai-studio': ['google ai studio', 'gemini api', 'google ai'],
    'groq': ['groq'],
    'hoop': ['hoop'],
    'inngest': ['inngest'],
    'laravel': ['laravel'],
    'llmgateway': ['llm gateway', 'llmgateway'],
    'netlify': ['netlify'],
    'neon': ['neon', 'neon database'],
    'nue': ['nue'],
    'nuxtlabs': ['nuxt', 'nuxtlabs'],
    'openstatus': ['openstatus'],
    'planetscale': ['planetscale'],
    'posthog': ['posthog'],
    'prisma': ['prisma'],
    'railway': ['railway'],
    'resend': ['resend'],
    'sanity': ['sanity'],
    'shadcn': ['shadcn', 'shadcn/ui'],
    'sst': ['sst'],
    'stripe': ['stripe'],
    'supabase': ['supabase', '@supabase/'],
    'tailwindlabs': ['tailwind', 'tailwindcss', 'tailwind labs'],
    'triggerdev': ['trigger.dev', 'triggerdev'],
    'turbo': ['turbo', 'turborepo'],
    'vercel': ['vercel', 'next.js', 'nextjs'],
    'workos': ['workos', 'work os'],
}


class EcosystemMatcher:
    def __init__(self, directory: ContactDirectory) -> None:
        self.directory = directory

    def match(self, repo: RepoProfile, readme: str, signals: Dict) -> List[EcosystemMatch]:
        haystack_parts = [
            repo.full_name,
            repo.description,
            readme[:16000],
            ' '.join(signals.get('terms', [])),
            ' '.join(signals.get('dependencies', [])),
            ' '.join(signals.get('frameworks', [])),
            ' '.join(signals.get('infra', [])),
            ' '.join(signals.get('links', [])),
        ]
        haystack = ' '.join(x.lower() for x in haystack_parts if x)
        scores: Dict[str, float] = defaultdict(float)
        reasons: Dict[str, List[str]] = defaultdict(list)
        matched_terms: Dict[str, List[str]] = defaultdict(list)

        for company_id in self.directory.company_ids():
            aliases = list(dict.fromkeys([company_id, self.directory.get_company(company_id).get('name', '')] + ALIASES.get(company_id, [])))
            for raw in aliases:
                alias = raw.lower().strip()
                if not alias:
                    continue
                if alias in haystack:
                    weight = 0.28 if len(alias) > 4 else 0.16
                    scores[company_id] += weight
                    matched_terms[company_id].append(raw)
                    if len(reasons[company_id]) < 5:
                        reasons[company_id].append(f"Matched ecosystem term '{raw}'.")

        # extra signal bonuses
        frameworks = set(signals.get('frameworks', []))
        dependencies = ' '.join(signals.get('dependencies', []))
        for company_id in list(scores):
            if company_id in frameworks:
                scores[company_id] += 0.24
                reasons[company_id].append('Framework/dependency signals align strongly.')
            if company_id in dependencies:
                scores[company_id] += 0.12
            if repo.owner_login and company_id.replace('-', '').lower() in repo.owner_login.lower().replace('-', ''):
                scores[company_id] += 0.22
                reasons[company_id].append('Repository owner name resembles ecosystem/company name.')

        matches: List[EcosystemMatch] = []
        for company_id, raw_score in scores.items():
            if raw_score < 0.20:
                continue
            company = self.directory.get_company(company_id) or {}
            confidence = min(0.98, round(raw_score, 3))
            matches.append(EcosystemMatch(
                company_id=company_id,
                company_name=company.get('name', company_id),
                confidence=confidence,
                reasons=reasons[company_id][:5],
                matched_terms=list(dict.fromkeys(matched_terms[company_id]))[:8],
            ))
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches[:6]
