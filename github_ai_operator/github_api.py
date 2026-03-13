from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, List, Optional

import requests

from .models import RepoProfile

GITHUB_API = 'https://api.github.com'
HEADERS = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
}


class GitHubClient:
    def __init__(self, token: Optional[str] = None) -> None:
        token = token or os.getenv('GITHUB_TOKEN')
        if not token:
            raise RuntimeError('GITHUB_TOKEN is required')
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.headers['Authorization'] = f'Bearer {token}'
        self.session.headers['User-Agent'] = 'github-ai-operator/3.0'

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        resp = self.session.request(method, url, timeout=60, **kwargs)
        if resp.status_code in (403, 429):
            remaining = resp.headers.get('X-RateLimit-Remaining')
            reset = resp.headers.get('X-RateLimit-Reset')
            if remaining == '0' and reset:
                sleep_for = max(0, int(reset) - int(time.time())) + 2
                print(f'[rate-limit] sleeping {sleep_for}s')
                time.sleep(min(sleep_for, 300))
                resp = self.session.request(method, url, timeout=60, **kwargs)
        resp.raise_for_status()
        return resp

    def get_repo(self, full_name: str) -> RepoProfile:
        r = self._request('GET', f'{GITHUB_API}/repos/{full_name}')
        return self._to_repo(r.json())

    def get_readme(self, full_name: str) -> str:
        r = self._request('GET', f'{GITHUB_API}/repos/{full_name}/readme')
        data = r.json()
        encoded = data.get('content', '')
        if encoded:
            return base64.b64decode(encoded).decode('utf-8', errors='ignore')
        return ''

    def get_contributing_rules(self, full_name: str) -> Dict[str, Any]:
        owner, repo = full_name.split('/', 1)
        candidates = [
            'CONTRIBUTING.md', '.github/CONTRIBUTING.md',
            '.github/ISSUE_TEMPLATE/bug_report.md',
            '.github/ISSUE_TEMPLATE/config.yml',
        ]
        found: Dict[str, Any] = {'files': [], 'content': {}}
        for path in candidates:
            url = f'{GITHUB_API}/repos/{owner}/{repo}/contents/{path}'
            resp = self.session.get(url, timeout=60)
            if resp.status_code == 200:
                body = resp.json()
                content = base64.b64decode(body.get('content', '')).decode('utf-8', errors='ignore')
                found['files'].append(path)
                found['content'][path] = content[:20000]
        return found

    def search_repositories(self, query: str, per_page: int = 10, page: int = 1, sort: str = 'updated', order: str = 'desc') -> List[RepoProfile]:
        r = self._request('GET', f'{GITHUB_API}/search/repositories', params={
            'q': query,
            'per_page': per_page,
            'page': page,
            'sort': sort,
            'order': order,
        })
        return [self._to_repo(item) for item in r.json().get('items', [])]

    def list_issues(self, full_name: str, state: str = 'open', per_page: int = 20) -> List[Dict[str, Any]]:
        r = self._request('GET', f'{GITHUB_API}/repos/{full_name}/issues', params={'state': state, 'per_page': per_page})
        return r.json()

    def get_top_contributors(self, full_name: str, per_page: int = 15) -> List[Dict[str, Any]]:
        r = self._request('GET', f'{GITHUB_API}/repos/{full_name}/contributors', params={'per_page': per_page})
        items = []
        for item in r.json():
            if not isinstance(item, dict):
                continue
            items.append({'login': item.get('login'), 'contributions': item.get('contributions', 0)})
        return items

    def get_issue_participants(self, full_name: str, per_page: int = 20) -> List[Dict[str, Any]]:
        users: Dict[str, Dict[str, Any]] = {}
        for issue in self.list_issues(full_name, state='all', per_page=per_page):
            if not isinstance(issue, dict):
                continue
            user = issue.get('user') or {}
            login = user.get('login')
            if login:
                users.setdefault(login, {'login': login, 'comments': 0})
                users[login]['comments'] += int(issue.get('comments', 0) or 0)
        return sorted(users.values(), key=lambda x: (-int(x.get('comments', 0)), str(x.get('login', '')).lower()))[:15]

    def create_issue(self, full_name: str, title: str, body: str, labels: Optional[List[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {'title': title, 'body': body}
        if labels:
            payload['labels'] = labels
        r = self._request('POST', f'{GITHUB_API}/repos/{full_name}/issues', json=payload)
        return r.json()

    @staticmethod
    def _to_repo(item: Dict[str, Any]) -> RepoProfile:
        owner = item.get('owner') or {}
        return RepoProfile(
            full_name=item['full_name'],
            html_url=item['html_url'],
            clone_url=item['clone_url'],
            description=item.get('description') or '',
            language=item.get('language'),
            stars=item.get('stargazers_count', 0),
            topics=item.get('topics', []),
            default_branch=item.get('default_branch'),
            archived=bool(item.get('archived')),
            disabled=bool(item.get('disabled')),
            fork=bool(item.get('fork')),
            open_issues_count=int(item.get('open_issues_count', 0)),
            owner_login=owner.get('login'),
            homepage=item.get('homepage'),
            pushed_at=item.get('pushed_at'),
            created_at=item.get('created_at'),
            updated_at=item.get('updated_at'),
        )
