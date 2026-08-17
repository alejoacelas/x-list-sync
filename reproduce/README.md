# Reproduce

The selected sources came from Alejo's “everything up to Karpathy” cutoff in the cost-ranked list: Patrick Collison, Agnes Callard, Luca de Leo, Tyler Cowen, Gavin Leech, Amanda Askell, Paul Graham, Nabeel Qureshi, and Andrej Karpathy. Ryan Greenblatt is already complete.

The implementation uses X API v2 user-context authentication:

1. Resolve each source handle.
2. Page through `GET /2/users/{id}/following` and checkpoint IDs locally.
3. Reuse existing Lists or create private Lists for missing targets.
4. Read existing members for the three partial Lists.
5. Add missing IDs with `POST /2/lists/{id}/members`, stopping before the configured budget and waiting between 295-write windows.

The projected $80.34 total and default $81 cap use X's August 2026 prices: $0.01 per user or following resource, $0.005 per List-management write, $0.005 per List-member resource, and $0.01 per List creation. Live growth can increase the total, so the sync stops before the cap and can resume after more credit is added.
