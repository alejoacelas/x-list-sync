# REPLICATE

## Finish the workspace migration

The human wanted the remaining folder reorganization finished and authorized interrupting conflicting sessions.

- Preserved this repository and its instruction wording, declared the tools group, and made CLAUDE.md import AGENTS.md. Its current path is /Users/alejo/best/tools/active/twitter/x-list-sync.

Agent session 01a072fe-84d6-73f3-b37e-3bb912088c38 · Commits x-list-sync: f5c8e6e

## Agent instructions cleanup — 2026-09-19

Alejo asked to refresh project instructions and remove redundant Claude instruction files where native AGENTS.md loading is available.

- Updated the applicable instructions and removed redundant local Claude copies; distinct content and preserved snapshots remain.
- Checked instruction references and shared-context freshness; native Claude loading requires 2.1.277+ with the built-in feature enabled.

Agent session 01a0b915-3eb2-78b2-9add-6ba48ad9a3b1 · Commits 1059478005002bddc84ce1efe9583d29095a1ece

## Explicit startup instructions

Alejo wanted shared instructions selected deliberately at startup, without copied text or automatic parent inheritance.

- Removed agent-context YAML and generated shared text; retained project-specific instructions locally.
- Shared groups: tools. Selection now lives in the machine's context registry; startup does not rewrite this file.

Agent session 01a0b915-3eb2-78b2-9add-6ba48ad9a3b1 · Commits 3b144af

<a id="construction-records"></a>

## Construction records

Preserved records from the former construction-notes folder.

<a id="record-readme"></a>

### Reproduce

The selected sources came from Alejo's “everything up to Karpathy” cutoff in the cost-ranked list: Patrick Collison, Agnes Callard, Luca de Leo, Tyler Cowen, Gavin Leech, Amanda Askell, Paul Graham, Nabeel Qureshi, and Andrej Karpathy. Ryan Greenblatt is already complete.

The implementation uses X API v2 user-context authentication:

1. Resolve each source handle.
2. Page through `GET /2/users/{id}/following` and checkpoint IDs locally.
3. Reuse existing Lists or create private Lists for missing targets.
4. Read existing members for the three partial Lists.
5. Add missing IDs with `POST /2/lists/{id}/members`, stopping before the configured budget and waiting between 295-write windows.

The projected $80.34 total and default $81 cap use X's August 2026 prices: $0.01 per user or following resource, $0.005 per List-management write, $0.005 per List-member resource, and $0.01 per List creation. Live growth can increase the total, so the sync stops before the cap and can resume after more credit is added.

## Retire construction folders

Alejo wanted all `reproduce` folders under `~/best` transitioned to `REPLICATE.md`.

- Consolidated the existing records and updated references for `reproduce`. Preserved scripts, data and maintained procedures in their own folders.
- Original tracked files remain in Git at `cdf5a7a84892d7bf19a4d1968dd78bfe9ac6f04e`; a full local backup, including ignored files, is at `/Users/alejo/.local/state/reproduce-migration/2026-09-19-_qyg4u7a/before/tools/active/twitter/x-list-sync`.

Agent session 01a0bb8d-6d31-76d3-ac4e-aca4c5dfce64 · Commits 8142ad5ae707e5ef0257265642423bf19ee08656
