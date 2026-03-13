from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def source_registry() -> List[Dict[str, Any]]:
    return [
        {
            "name": "GitHub",
            "role": "primary discovery and repo intelligence",
            "automation": "read/write",
            "free_tier": True,
            "included": True,
            "notes": "Search, metadata, contributors, issues, pull requests, and issue drafting.",
        },
        {
            "name": "Reddit",
            "role": "community distribution",
            "automation": "write with OAuth and policy constraints",
            "free_tier": True,
            "included": True,
            "notes": "Approval-gated only; subreddit rules matter.",
        },
        {
            "name": "Bluesky",
            "role": "short-form distribution",
            "automation": "write",
            "free_tier": True,
            "included": True,
            "notes": "Strong fit for developer and open-source announcements.",
        },
        {
            "name": "Mastodon",
            "role": "short-form distribution",
            "automation": "write",
            "free_tier": True,
            "included": True,
            "notes": "Instance-specific base URL and token required.",
        },
        {
            "name": "DEV",
            "role": "article publishing",
            "automation": "write",
            "free_tier": True,
            "included": True,
            "notes": "Useful for dev logs and repo spotlights.",
        },
        {
            "name": "Hashnode",
            "role": "article publishing",
            "automation": "write",
            "free_tier": True,
            "included": True,
            "notes": "GraphQL publishing path.",
        },
        {
            "name": "Medium",
            "role": "article publishing",
            "automation": "write",
            "free_tier": True,
            "included": True,
            "notes": "Best for long-form summaries and launch notes.",
        },
        {
            "name": "Discord",
            "role": "community push",
            "automation": "write via webhook",
            "free_tier": True,
            "included": True,
            "notes": "Only channels you control or are explicitly invited to.",
        },
        {
            "name": "Matrix",
            "role": "community push",
            "automation": "write",
            "free_tier": True,
            "included": True,
            "notes": "Open federation-friendly room posting.",
        },
        {
            "name": "Nostr",
            "role": "decentralized short-form distribution",
            "automation": "bridge-based write",
            "free_tier": True,
            "included": True,
            "notes": "Current package uses an HTTP bridge pattern.",
        },
        {
            "name": "RSS",
            "role": "syndication",
            "automation": "generate feed",
            "free_tier": True,
            "included": True,
            "notes": "Useful for secondary ingestion and personal sites.",
        },
        {
            "name": "Generic Webhook",
            "role": "custom sinks",
            "automation": "write",
            "free_tier": True,
            "included": True,
            "notes": "Lets you bridge into your own stack.",
        },
        {
            "name": "Hacker News",
            "role": "discovery and manual follow-through",
            "automation": "read-oriented",
            "free_tier": True,
            "included": False,
            "notes": "No standard official unattended submission path in this package.",
        },
        {
            "name": "Lobsters",
            "role": "discovery and manual follow-through",
            "automation": "mostly manual submission",
            "free_tier": True,
            "included": False,
            "notes": "Better treated as a human-reviewed target.",
        },
        {
            "name": "Stack Exchange",
            "role": "question discovery",
            "automation": "read",
            "free_tier": True,
            "included": False,
            "notes": "Not suitable for unattended answer spam.",
        },
    ]


def write_source_registry(output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "source_registry.json"
    path.write_text(json.dumps(source_registry(), indent=2), encoding="utf-8")
    md = ["# Source Registry", "", "This file summarizes which free/public outlets are supported directly and which are better treated as review-only targets.", ""]
    for item in source_registry():
        md.extend([
            f"## {item['name']}",
            f"- Role: {item['role']}",
            f"- Automation: {item['automation']}",
            f"- Free tier: {item['free_tier']}",
            f"- Included: {item['included']}",
            f"- Notes: {item['notes']}",
            "",
        ])
    (output_dir / "SOURCE_REGISTRY.md").write_text("\n".join(md), encoding="utf-8")
    return path
