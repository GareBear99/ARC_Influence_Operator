from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .models import RepoAssessment


SAFE_STATUS = {"drafted", "retry", "failed"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-").lower() or "default"


class PublisherManager:
    def __init__(self, distribution_cfg, output_dir: Path, pacer=None) -> None:
        self.cfg = distribution_cfg
        self.output_dir = Path(output_dir)
        self.pacer = pacer
        self.publish_dir = self.output_dir / "publish"
        self.publish_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path = self.output_dir / "publish_queue.json"
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "arc-influence-operator/5.0"

    def stage_assessment(self, assessment: RepoAssessment) -> List[Path]:
        if not self.cfg.enabled or not self.cfg.stage_packets:
            return []
        if not assessment.rank:
            return []
        if assessment.rank.social_score < self.cfg.min_social_score:
            return []
        if not assessment.plan or not assessment.plan.recommended_people:
            return []

        drafts: List[Path] = []
        outlet_names = [
            "reddit",
            "bluesky",
            "mastodon",
            "devto",
            "hashnode",
            "medium",
            "discord",
            "matrix",
            "nostr",
            "rss",
            "webhook",
        ]
        for outlet_name in outlet_names:
            outlet_cfg = getattr(self.cfg, outlet_name)
            if not outlet_cfg.enabled:
                continue
            for payload in self._build_outlet_payloads(assessment, outlet_name, outlet_cfg):
                path = self.publish_dir / f"{payload['id']}.json"
                path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                drafts.append(path)
        self._refresh_queue_index()
        return drafts

    def _refresh_queue_index(self) -> None:
        items: List[Dict[str, Any]] = []
        for path in sorted(self.publish_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "id": payload.get("id"),
                    "repo": payload.get("repo"),
                    "outlet": payload.get("outlet"),
                    "destination": payload.get("destination"),
                    "status": payload.get("status"),
                    "approved": payload.get("approved", False),
                    "path": str(path),
                })
            except Exception:
                continue
        self.queue_path.write_text(json.dumps(items, indent=2), encoding="utf-8")


    def publish_payload_file(self, path: str | Path) -> Dict[str, Any]:
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = self._publish_one(payload)
        payload["status"] = result["status"]
        payload["published_at"] = datetime.now(timezone.utc).isoformat()
        payload["publish_result"] = result
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._refresh_queue_index()
        return result
    def publish_pending(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        count = 0
        for path in sorted(self.publish_dir.glob("*.json")):
            if count >= self.cfg.max_posts_per_run:
                break
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("status") not in SAFE_STATUS:
                continue
            mode = payload.get("mode", "draft_only")
            approved = bool(payload.get("approved", False))
            if mode == "draft_only":
                continue
            if mode == "approved_only" and not approved:
                continue
            result = self._publish_one(payload)
            payload["status"] = result["status"]
            payload["published_at"] = datetime.now(timezone.utc).isoformat()
            payload["publish_result"] = result
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            results.append(result)
            if result["status"] == "posted":
                count += 1
        self._refresh_queue_index()
        return results

    def _build_outlet_payloads(self, assessment: RepoAssessment, outlet_name: str, outlet_cfg) -> List[Dict[str, Any]]:
        repo = assessment.repo
        people = assessment.plan.recommended_people[: outlet_cfg.max_targets or 4]
        short_handles = [p for p in people if p.startswith("@")][:4]
        title_base = f"{repo.full_name}: {assessment.review.summary[:110].strip()}"
        long_md = self._build_article_markdown(assessment)
        short_text = self._build_short_text(assessment, outlet_name, short_handles)
        tags = self._build_tags(assessment, outlet_cfg.tags)
        destinations = outlet_cfg.destinations or [""]
        drafts: List[Dict[str, Any]] = []
        for destination in destinations:
            draft_id = _slug(f"{repo.full_name}-{outlet_name}-{destination or 'default'}")
            body = long_md if outlet_name in {"devto", "hashnode", "medium"} else short_text
            payload = {
                "id": draft_id,
                "repo": repo.full_name,
                "repo_url": repo.html_url,
                "outlet": outlet_name,
                "destination": destination,
                "mode": outlet_cfg.mode,
                "approved": False,
                "status": "drafted",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "title": f"{outlet_cfg.title_prefix}{title_base}".strip(),
                "body": body,
                "tags": tags,
                "social_score": round(float(assessment.rank.social_score), 4) if assessment.rank else 0.0,
                "strategy_profile": assessment.plan.strategy_profile,
                "recommended_people": people,
                "ecosystems": [asdict(x) for x in assessment.ecosystem_matches[:3]],
                "operator_notes": list(assessment.plan.operator_notes[:6]),
                "platform_payload": self._platform_payload(outlet_name, destination, title_base, body, tags),
            }
            drafts.append(payload)
        return drafts

    def _build_short_text(self, assessment: RepoAssessment, outlet_name: str, handles: List[str]) -> str:
        repo = assessment.repo
        ecos = [m.company_name for m in assessment.ecosystem_matches[:2]]
        eco_text = f" | ecosystems: {', '.join(ecos)}" if ecos else ""
        handle_text = f" {' '.join(handles)}" if handles else ""
        text = (
            f"Scouted {repo.full_name}: {assessment.review.summary} "
            f"Top next step: {assessment.plan.action}."
            f"{eco_text}\n{repo.html_url}{handle_text}"
        )
        if outlet_name == "reddit":
            return (
                f"Repo: {repo.full_name}\n\n"
                f"Why it stood out: {assessment.review.summary}\n\n"
                f"Suggested next step: {assessment.plan.action}\n"
                f"Top improvements: {'; '.join(assessment.review.improvements[:3]) or 'n/a'}\n"
                f"URL: {repo.html_url}\n"
            )
        return text[:280] if outlet_name == "bluesky" else text[:500]

    def _build_article_markdown(self, assessment: RepoAssessment) -> str:
        repo = assessment.repo
        lines = [
            f"# Scout note: {repo.full_name}",
            "",
            assessment.review.summary,
            "",
            f"Repo: {repo.html_url}",
            "",
            "## Why it matched",
        ]
        lines.extend(f"- {r}" for r in assessment.rank.reasons[:6] if assessment.rank)
        lines.extend([
            "",
            "## Ecosystem matches",
        ])
        if assessment.ecosystem_matches:
            lines.extend(f"- {m.company_name} ({m.confidence:.2f})" for m in assessment.ecosystem_matches[:3])
        else:
            lines.append("- None")
        lines.extend([
            "",
            "## Suggested improvements",
        ])
        lines.extend(f"- {x}" for x in assessment.review.improvements[:5])
        lines.extend([
            "",
            "## Operator notes",
        ])
        lines.extend(f"- {x}" for x in assessment.plan.operator_notes[:5])
        lines.append("")
        return "\n".join(lines)

    def _build_tags(self, assessment: RepoAssessment, configured: List[str]) -> List[str]:
        tags = [t.lower().replace(" ", "-") for t in configured[:4]]
        for match in assessment.ecosystem_matches[:3]:
            tag = _slug(match.company_name).replace("_", "-")
            if tag and tag not in tags:
                tags.append(tag)
        for topic in assessment.repo.topics[:3]:
            tag = _slug(topic).replace("_", "-")
            if tag and tag not in tags:
                tags.append(tag)
        return tags[:4]

    def _platform_payload(self, outlet_name: str, destination: str, title: str, body: str, tags: List[str]) -> Dict[str, Any]:
        if outlet_name == "reddit":
            return {"kind": "self", "sr": destination, "title": title[:300], "text": body}
        if outlet_name == "bluesky":
            return {"text": body}
        if outlet_name == "mastodon":
            return {"status": body, "visibility": "public"}
        if outlet_name == "devto":
            return {
                "article": {
                    "title": title[:150],
                    "published": False,
                    "body_markdown": body,
                    "tags": tags,
                }
            }
        if outlet_name == "hashnode":
            return {
                "query": "mutation PublishPost($input: PublishPostInput!) { publishPost(input: $input) { post { id slug url } } }",
                "variables": {
                    "input": {
                        "title": title[:150],
                        "contentMarkdown": body,
                        "tags": [{"slug": t} for t in tags[:5]],
                        "publicationId": destination or None,
                    }
                },
            }
        if outlet_name == "medium":
            return {
                "title": title[:100],
                "contentFormat": "markdown",
                "content": body,
                "publishStatus": "public" if destination != "draft" else "draft",
                "tags": tags[:5],
            }
        if outlet_name == "discord":
            return {"content": f"**{title}**\n{body}"[:1900]}
        if outlet_name == "matrix":
            return {
                "msgtype": "m.text",
                "body": f"{title}\n\n{body}",
            }
        if outlet_name == "nostr":
            return {
                "content": f"{title}\n\n{body}",
                "tags": [["t", t] for t in tags[:5]],
            }
        if outlet_name == "rss":
            return {"title": title, "body": body, "tags": tags, "destination": destination or "arc-influence-feed.xml"}
        if outlet_name == "webhook":
            return {"title": title, "body": body, "tags": tags, "destination": destination}
        return {"title": title, "body": body, "tags": tags}

    def _publish_one(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.pacer is not None:
            self.pacer.before_issue()
        outlet = payload.get("outlet")
        try:
            if outlet == "reddit":
                return self._post_reddit(payload)
            if outlet == "bluesky":
                return self._post_bluesky(payload)
            if outlet == "mastodon":
                return self._post_mastodon(payload)
            if outlet == "devto":
                return self._post_devto(payload)
            if outlet == "hashnode":
                return self._post_hashnode(payload)
            if outlet == "medium":
                return self._post_medium(payload)
            if outlet == "discord":
                return self._post_discord(payload)
            if outlet == "matrix":
                return self._post_matrix(payload)
            if outlet == "nostr":
                return self._post_nostr(payload)
            if outlet == "rss":
                return self._post_rss(payload)
            if outlet == "webhook":
                return self._post_webhook(payload)
            return {"status": "skipped", "reason": f"Unsupported outlet: {outlet}"}
        except Exception as exc:
            return {"status": "failed", "reason": str(exc)}

    def _post_reddit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        token = os.getenv("REDDIT_ACCESS_TOKEN")
        if not token:
            return {"status": "failed", "reason": "REDDIT_ACCESS_TOKEN missing"}
        sr = payload.get("destination")
        if not sr:
            return {"status": "failed", "reason": "Reddit destination missing"}
        resp = self._session.post(
            "https://oauth.reddit.com/api/submit",
            headers={"Authorization": f"Bearer {token}"},
            data={**payload["platform_payload"], "api_type": "json", "resubmit": True},
            timeout=60,
        )
        if resp.status_code >= 400:
            return {"status": "failed", "reason": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        return {"status": "posted", "response": resp.json()}

    def _post_bluesky(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        handle = os.getenv("BLUESKY_HANDLE")
        password = os.getenv("BLUESKY_APP_PASSWORD")
        pds_host = os.getenv("BLUESKY_PDS_HOST", "https://bsky.social")
        if not handle or not password:
            return {"status": "failed", "reason": "BLUESKY_HANDLE or BLUESKY_APP_PASSWORD missing"}
        session = self._session.post(
            f"{pds_host}/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
            timeout=60,
        )
        session.raise_for_status()
        session_data = session.json()
        did = session_data["did"]
        jwt = session_data["accessJwt"]
        record = {
            "$type": "app.bsky.feed.post",
            "text": payload["platform_payload"]["text"],
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        resp = self._session.post(
            f"{pds_host}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"repo": did, "collection": "app.bsky.feed.post", "record": record},
            timeout=60,
        )
        if resp.status_code >= 400:
            return {"status": "failed", "reason": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        return {"status": "posted", "response": resp.json()}

    def _post_mastodon(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        token = os.getenv("MASTODON_ACCESS_TOKEN")
        api_base = os.getenv("MASTODON_API_BASE") or self.cfg.mastodon.api_base
        if not token or not api_base:
            return {"status": "failed", "reason": "MASTODON_ACCESS_TOKEN or MASTODON_API_BASE missing"}
        resp = self._session.post(
            f"{api_base.rstrip('/')}/api/v1/statuses",
            headers={"Authorization": f"Bearer {token}"},
            data=payload["platform_payload"],
            timeout=60,
        )
        if resp.status_code >= 400:
            return {"status": "failed", "reason": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        return {"status": "posted", "response": resp.json()}

    def _post_devto(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        api_key = os.getenv("DEVTO_API_KEY")
        if not api_key:
            return {"status": "failed", "reason": "DEVTO_API_KEY missing"}
        article = dict(payload["platform_payload"]["article"])
        article["published"] = payload.get("mode") == "auto"
        resp = self._session.post(
            "https://dev.to/api/articles",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={"article": article},
            timeout=60,
        )
        if resp.status_code >= 400:
            return {"status": "failed", "reason": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        return {"status": "posted", "response": resp.json()}

    def _post_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = os.getenv("GENERIC_OUTLET_WEBHOOK_URL") or payload.get("destination")
        if not url:
            return {"status": "failed", "reason": "Webhook destination missing"}
        resp = self._session.post(url, json=payload["platform_payload"], timeout=60)
        if resp.status_code >= 400:
            return {"status": "failed", "reason": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        return {"status": "posted", "response": resp.text[:500]}
