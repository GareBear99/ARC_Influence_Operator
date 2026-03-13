# github_ai_operator

Repo discovery, assessment, ecosystem matching, maintainer graphing, strategy-aware human recommendation, cooldown memory, static dashboard generation, staged publishing packets, and an approval queue UI.

## v7 additions
- `queue_ui.py` local review server
- browser-based queue editing and approval
- per-packet publish action from the queue UI
- `source_registry.py` to document supported vs review-only free/public outlets
- automatic `source_registry.json` and `SOURCE_REGISTRY.md` output on each run

## Safety posture
This package is meant to discover and prepare, not mass-contact people.
Publishing defaults to staged / approval-gated workflows.

## Queue workflow
1. Run the scout to generate reports and staged outlet packets.
2. Launch the queue UI.
3. Edit the copy you want.
4. Approve the packets you actually want to send.
5. Publish from the UI or with publish mode.

## Commands
```bash
python scout.py --config config.json
python scout.py --config config.json --publish-pending
python scout.py --config config.json --only-publish-pending
python scout.py --config config.json --serve-queue
```

## Environment variables
- `GITHUB_TOKEN`
- `REDDIT_ACCESS_TOKEN`
- `BLUESKY_HANDLE`
- `BLUESKY_APP_PASSWORD`
- `BLUESKY_PDS_HOST` (optional)
- `MASTODON_ACCESS_TOKEN`
- `MASTODON_API_BASE`
- `DEVTO_API_KEY`
- `HASHNODE_PAT`
- `HASHNODE_ENDPOINT`
- `MEDIUM_ACCESS_TOKEN`
- `MEDIUM_USER_ID`
- `DISCORD_WEBHOOK_URL`
- `MATRIX_ACCESS_TOKEN`
- `MATRIX_HOMESERVER`
- `MATRIX_ROOM_ID`
- `NOSTR_RELAY_HTTP_URL`
- `GENERIC_OUTLET_WEBHOOK_URL`

## Outlet notes
- **Directly supported in this package**: GitHub, Reddit, Bluesky, Mastodon, DEV, Hashnode, Medium, Discord webhook, Matrix, Nostr bridge, RSS, generic webhooks.
- **Documented but not write-enabled here**: Hacker News, Lobsters, Stack Exchange.
- Best practice remains: stage -> review -> approve -> publish.
