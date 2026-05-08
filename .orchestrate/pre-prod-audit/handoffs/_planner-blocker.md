<!-- planner-authored note (not a worker handoff) -->

# Pre-prod audit: orchestrate planner blocker

## Status
blocked — orchestrate loop cannot run in this Cloud Agent VM

## Reason
`CURSOR_API_KEY` is not set in the environment. The orchestrate loop
(`scripts/cli.ts run --root <workspace>`) requires it to spawn cloud
agents via `@cursor/sdk` (see `core/agent-manager.ts` line ~225 and
`cursor-sdk` skill > Auth).

`SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are also unset, but those are
optional — Slack visibility would simply be disabled.

## What was done

1. Read the orchestrate `SKILL.md` and `references/planner.md`.
2. Discovered the workspace:
   - Stack: Django 4.2 (Python 3.12) backend + React 18 (CRA / react-scripts 5)
     frontend, packaged in two Dockerfiles, glued by `docker-compose.backend.yml`
     and `frontend/nginx.conf*`.
   - Env files: `.env.example`, `env.backend`, `backend/env.example` —
     three sources of truth that need cross-checking.
   - CI: `.github/workflows/backend.yml` only (no frontend workflow).
3. Authored `plan.json` (5 tasks):
   - `audit-env-config` — cross-check env files, Dockerfiles, settings.py,
     nginx config, docker-compose, CI workflows. Output: `docs/audits/env-config-audit-2026-05.md`.
   - `audit-package-versions` — Python/JS/base-image versions + CVE / EOL
     check (notably Node 18 is EOL since 2025-04-30, CRA is archived,
     Django 4.2 LTS support ends 2026-04). Output: `docs/audits/packages-audit-2026-05.md`.
   - `audit-local-build` — actual `pip install`, `manage.py check/migrate/collectstatic`,
     `npm ci && npm run build`, capture logs. Output: `docs/audits/local-build-report-2026-05.md` + raw logs.
   - `audit-file-compat` — API contract diff (`backend/parser_app/urls.py` vs
     `frontend/src/api.js`), upload mime-type/extension support, auth
     cookies/CSRF/CORS, static asset routing for `index.html` / `admin.html` /
     `taps.html`, upload size limits. Output: `docs/audits/file-compat-audit-2026-05.md`.
   - `aggregate-prod-readiness` (depends on the four above) — rolls up
     blockers / risks / nice-to-haves into `docs/PROD_READINESS_2026-05.md`,
     opens its own draft PR.
4. Validated `plan.json` parses cleanly with `cli.ts tree` (5 pending tasks
   in the expected dependency shape).
5. Wrote this blocker note + `attention.log` so the next agent run picks
   up the situation.

## How to unblock

1. In Cursor Dashboard > Cloud Agents > Secrets, add `CURSOR_API_KEY`
   (personal/user key from Cursor Dashboard > Integrations). Repo-scoped
   or user-scoped both work; user-scoped overrides team.
2. Optionally add `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` for run-thread
   visibility (Slack scopes listed in `references/planner.md`).
3. Spawn a follow-up cloud agent with the same root-planner prompt
   (or start a new `/orchestrate` run pointing at this same workspace).
   The next `bun cli.ts run --root .orchestrate/pre-prod-audit` will
   resume from `state.json` and start spawning the four parallel
   audit workers.

## Selfcheck
- `plan.selfAgentId` set to `bc-332293e3-ac11-48b5-aa16-4ec1dbe76627`
  (this planner) so the next loop's children will be linked under
  this lineage and `kill-tree --agent-id` can target this subtree.
- `syncStateToGit: true` so future runs commit state/handoffs into the
  feature branch automatically.
