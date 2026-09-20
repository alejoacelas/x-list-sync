# X List sync decisions

## Core decisions

### Bounded changes

- [Keep the selected source list explicit and Lists private](#decision-1).
- [Check the spending ceiling before each API operation](#decision-2).

### Resumability

- [Checkpoint successful pages and writes](#decision-3).
- [Pace writes across the window instead of bursting](#decision-4).

## Details

<a id="decision-1"></a>

### Keep the selected source list explicit and Lists private

The authorized run covers the nine sources through Karpathy in the recorded selection; Ryan Greenblatt was already complete. Reuse existing Lists, inspect partial membership and add missing IDs instead of recreating Lists or expanding targets implicitly. See [src/x_list_sync.py](src/x_list_sync.py).

<a id="decision-2"></a>

### Check the spending ceiling before each API operation

The $81 default cap and $80.34 projection are based on the saved August pricing and counts. Growth or price changes require a revised plan; estimated costs and budget checks do not establish current provider billing. See [README.md](README.md).

<a id="decision-3"></a>

### Checkpoint successful pages and writes

Retain progress so interruption does not repeat completed work or charge for re-reading everything. Reconcile known membership before adding, and preserve explicit handling for ineligible members. See [src/x_list_sync.py](src/x_list_sync.py).

<a id="decision-4"></a>

### Pace writes across the window instead of bursting

The limiter was changed from 295-write batches to spacing calls across 900 seconds. Preserve reported rate-limit response details and stop/error handling rather than treating failed writes as successful membership. See [tests/test_sync.py](tests/test_sync.py). History inspected: [e82aff7](https://github.com/alejoacelas/x-list-sync/commit/e82aff7), [8033936](https://github.com/alejoacelas/x-list-sync/commit/8033936).
