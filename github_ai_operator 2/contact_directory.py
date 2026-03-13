from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Contact


class ContactDirectory:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).parent / 'data' / 'companies'
        self.data_dir = Path(data_dir)
        self.companies: Dict[str, Dict] = {}
        self._contacts: Dict[str, List[Contact]] = {}
        self._load()

    def _load(self) -> None:
        for path in sorted(self.data_dir.glob('*.json')):
            try:
                obj = json.loads(path.read_text(encoding='utf-8'))
            except Exception:
                continue
            company_id = obj.get('id') or path.stem
            obj['id'] = company_id
            self.companies[company_id] = obj
            contacts: List[Contact] = []
            for cat in obj.get('categories', []):
                category = str(cat.get('name', '')).strip() or 'General'
                for item in cat.get('contacts', []):
                    handles = [str(h).strip() for h in item.get('handles', []) if str(h).strip()]
                    if not handles:
                        continue
                    contacts.append(Contact(
                        company_id=company_id,
                        company_name=obj.get('name', company_id),
                        category=category,
                        product=str(item.get('product', '')).strip() or category,
                        handles=handles,
                    ))
            self._contacts[company_id] = contacts

    def company_ids(self) -> List[str]:
        return sorted(self.companies)

    def has_company(self, company_id: str) -> bool:
        return company_id in self.companies

    def get_company(self, company_id: str) -> Optional[Dict]:
        return self.companies.get(company_id)

    def get_company_contacts(self, company_id: str) -> List[Contact]:
        return list(self._contacts.get(company_id, []))

    def all_contacts(self) -> List[Contact]:
        out: List[Contact] = []
        for items in self._contacts.values():
            out.extend(items)
        return out

    def get_contacts_by_role(self, company_id: str, role_hint: str) -> List[Contact]:
        hint = role_hint.lower().strip()
        out: List[Contact] = []
        for item in self.get_company_contacts(company_id):
            hay = f"{item.category} {item.product}".lower()
            if hint in hay:
                out.append(item)
        return out

    def get_best_contacts(self, company_id: str, intent: str) -> List[str]:
        intent = intent.lower().strip()
        contacts = self.get_company_contacts(company_id)
        if not contacts:
            return []

        priority_rules = {
            'showcase_build': ['official', 'general', 'community', 'devrel', 'founder', 'ceo'],
            'product_feedback': ['product', 'official', 'general', 'design', 'community'],
            'technical_help': ['devrel', 'engineering', 'framework', 'oss', 'product', 'official'],
            'community_visibility': ['community', 'devrel', 'official', 'general'],
            'relationship_build': ['general', 'community', 'devrel', 'official', 'product'],
        }
        priorities = priority_rules.get(intent, ['official', 'general', 'community', 'product'])

        def score(contact: Contact) -> tuple[int, int, str]:
            hay = f"{contact.category} {contact.product}".lower()
            best = 999
            for i, token in enumerate(priorities):
                if token in hay:
                    best = min(best, i)
            return (best, len(contact.handles), hay)

        ordered = sorted(contacts, key=score)
        seen = set()
        picked: List[str] = []
        for item in ordered:
            for handle in item.handles:
                key = handle.lower()
                if key not in seen:
                    seen.add(key)
                    picked.append(handle)
                if len(picked) >= 6:
                    return picked
        return picked

    def to_summary(self, company_id: str) -> Dict:
        company = self.get_company(company_id) or {}
        return {
            'id': company_id,
            'name': company.get('name', company_id),
            'description': company.get('description', ''),
            'contacts': [asdict(x) for x in self.get_company_contacts(company_id)],
        }
