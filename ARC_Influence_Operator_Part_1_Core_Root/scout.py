#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random

from github_ai_operator.config import AppConfig
from github_ai_operator.delay import HumanPacer
from github_ai_operator.engine import OperatorEngine
from github_ai_operator.github_api import GitHubClient
from github_ai_operator.queue_ui import serve_queue_ui


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='GitHub AI operator: scout, stage, publish, and queue review UI')
    p.add_argument('--config', required=True, help='Path to config JSON')
    p.add_argument('--print-queries', action='store_true', help='Only print generated queries')
    p.add_argument('--publish-pending', action='store_true', help='Publish staged drafts that are auto-mode or approved')
    p.add_argument('--only-publish-pending', action='store_true', help='Skip scanning and only publish staged drafts')
    p.add_argument('--serve-queue', action='store_true', help='Serve the local approval queue UI')
    p.add_argument('--queue-host', default='127.0.0.1', help='Host for the queue UI server')
    p.add_argument('--queue-port', type=int, default=8765, help='Port for the queue UI server')
    p.add_argument('--no-browser', action='store_true', help='Do not auto-open the queue UI in a browser')
    p.add_argument('--seed', type=int, default=1337, help='Random seed for pacing jitter')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = AppConfig.from_json(args.config)
    gh = GitHubClient()
    pacer = HumanPacer(cfg.delay_profile, random.Random(args.seed))
    engine = OperatorEngine(cfg, gh, pacer)
    if args.print_queries:
        engine.print_queries()
        return
    if not args.only_publish_pending and not args.serve_queue:
        engine.run()
    if args.publish_pending or args.only_publish_pending:
        results = engine.publish_pending()
        print(f'[publish] attempted={len(results)}')
        for item in results:
            print(item)
    if args.serve_queue:
        publisher = engine.publisher if engine.publisher else None
        publish_dir = engine.output_dir / 'publish'
        serve_queue_ui(publish_dir, publisher=publisher, host=args.queue_host, port=args.queue_port, open_browser=not args.no_browser)


if __name__ == '__main__':
    main()
