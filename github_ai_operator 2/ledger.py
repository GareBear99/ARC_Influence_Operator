from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class OperatorLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {'repos': {}, 'contacts': {}, 'events': []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding='utf-8')

    def get_repo_record(self, full_name: str) -> Dict[str, Any]:
        return self.data.setdefault('repos', {}).setdefault(full_name, {'events': [], 'last_action': None, 'contacts': {}, 'last_timestamp': None})

    def last_action_for_repo(self, full_name: str) -> Optional[str]:
        return self.get_repo_record(full_name).get('last_action')

    def repo_in_cooldown(self, full_name: str, days: int) -> bool:
        record = self.get_repo_record(full_name)
        ts = record.get('last_timestamp')
        if not ts:
            return False
        try:
            last = datetime.fromisoformat(ts)
        except Exception:
            return False
        return datetime.now(timezone.utc) - last < timedelta(days=days)

    def filter_contacts_by_cooldown(self, full_name: str, contacts: Dict[str, list[str]], days: int) -> Dict[str, list[str]]:
        now = datetime.now(timezone.utc)
        out: Dict[str, list[str]] = {}
        global_contacts = self.data.setdefault('contacts', {})
        for company, handles in contacts.items():
            for handle in handles:
                key = handle.lower()
                ts = global_contacts.get(key, {}).get('last_used')
                blocked = False
                if ts:
                    try:
                        blocked = now - datetime.fromisoformat(ts) < timedelta(days=days)
                    except Exception:
                        blocked = False
                if not blocked:
                    out.setdefault(company, []).append(handle)
        return out

    def record(self, full_name: str, payload: Dict[str, Any]) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        event = {'repo': full_name, 'timestamp': ts, **payload}
        repo_record = self.get_repo_record(full_name)
        repo_record['events'].append(event)
        repo_record['last_action'] = payload.get('action')
        repo_record['last_timestamp'] = ts
        contacts = payload.get('recommended_contacts') or {}
        if contacts:
            repo_record['contacts'] = contacts
            global_contacts = self.data.setdefault('contacts', {})
            for handles in contacts.values():
                for handle in handles:
                    global_contacts.setdefault(handle.lower(), {})['last_used'] = ts
        self.data['events'].append(event)
        self.save()
