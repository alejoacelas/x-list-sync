# x-list-sync

I use this to finish selected private X Lists without losing progress or exceeding an $81 API budget. The current nine-list run is projected to cost $80.34 if live follow counts have not changed.

```sh
python -m venv .venv
.venv/bin/pip install -e . pytest
cp .env.example .env
.venv/bin/x-list-sync plan
.venv/bin/x-list-sync sync
```

The sync checkpoints every successful write and page, keeps credentials in the ignored `.env`, and waits before X's 300-write/15-minute limit.
