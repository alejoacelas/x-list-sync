from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import requests
from requests_oauthlib import OAuth1


ROOT = Path(__file__).resolve().parents[1]
API = "https://api.x.com/2"
STATE_PATH = ROOT / "data" / "state.json"
TARGETS_PATH = ROOT / "data" / "targets.json"
ROSTERS_DIR = ROOT / "data" / "rosters"

USER_READ = 0.010
FOLLOWING_READ = 0.010
LIST_READ = 0.005
LIST_CREATE = 0.010
LIST_MANAGE = 0.005


class XAPIError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, detail: str) -> None:
        super().__init__(f"{method} {path} -> {status}: {detail}")
        self.status = status


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


@dataclass
class Budget:
    limit: float
    spent: float = 0.0

    def require(self, amount: float, label: str) -> None:
        if self.spent + amount > self.limit + 1e-9:
            raise RuntimeError(
                f"Budget stop before {label}: ${self.spent:.3f} spent + "
                f"${amount:.3f} would exceed ${self.limit:.2f}"
            )

    def charge(self, amount: float) -> None:
        self.spent = round(self.spent + amount, 6)


class WriteLimiter:
    def __init__(self, limit: int = 295, window_seconds: int = 900) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.started = time.monotonic()
        self.used = 0

    def acquire(self) -> None:
        if self.used < self.limit:
            self.used += 1
            return
        remaining = self.window_seconds - (time.monotonic() - self.started) + 2
        if remaining > 0:
            print(f"Rate window full; waiting {remaining:.0f}s", flush=True)
            time.sleep(remaining)
        self.started = time.monotonic()
        self.used = 1


class XClient:
    def __init__(self, budget: Budget, limiter: WriteLimiter) -> None:
        needed = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
        missing = [name for name in needed if not os.environ.get(name)]
        if missing:
            raise RuntimeError("Missing credentials: " + ", ".join(missing))
        self.session = requests.Session()
        self.session.auth = OAuth1(
            os.environ["X_API_KEY"],
            os.environ["X_API_SECRET"],
            os.environ["X_ACCESS_TOKEN"],
            os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        self.budget = budget
        self.limiter = limiter

    def request(
        self,
        method: str,
        path: str,
        *,
        expected_cost: float,
        cost_label: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        is_write: bool = False,
    ) -> dict[str, Any]:
        self.budget.require(expected_cost, cost_label)
        if is_write:
            self.limiter.acquire()
        transient_failures = 0
        while True:
            try:
                response = self.session.request(
                    method,
                    API + path,
                    params=params,
                    json=body,
                    timeout=45,
                )
            except requests.RequestException as exc:
                transient_failures += 1
                if transient_failures >= 6:
                    raise
                delay = min(60, 2 ** (transient_failures - 1))
                print(
                    f"X connection error; retrying in {delay}s: {exc}",
                    flush=True,
                )
                time.sleep(delay)
                continue
            if response.status_code == 429:
                reset = int(response.headers.get("x-rate-limit-reset", "0") or 0)
                delay = max(5, reset - int(time.time()) + 2) if reset else 905
                limit = response.headers.get("x-rate-limit-limit", "unknown")
                remaining = response.headers.get("x-rate-limit-remaining", "unknown")
                reset_label = str(reset) if reset else "unknown"
                retry_after = response.headers.get("retry-after", "unknown")
                detail = response.text[:300].replace("\n", " ")
                print(
                    "X rate limit: "
                    f"limit={limit}, remaining={remaining}, reset={reset_label}; "
                    f"retry-after={retry_after}; waiting {delay}s; body={detail}",
                    flush=True,
                )
                time.sleep(delay)
                continue
            if response.status_code >= 500:
                transient_failures += 1
                if transient_failures >= 6:
                    detail = response.text[:1000]
                    raise XAPIError(method, path, response.status_code, detail)
                time.sleep(min(60, 2 ** (transient_failures - 1)))
                continue
            if not response.ok:
                detail = response.text[:1000]
                raise XAPIError(method, path, response.status_code, detail)
            self.budget.charge(expected_cost)
            return response.json()


def target_state(state: dict[str, Any], handle: str) -> dict[str, Any]:
    return state.setdefault("targets", {}).setdefault(handle.lower(), {})


def save_state(state: dict[str, Any], budget: Budget) -> None:
    state["estimated_spend_usd"] = budget.spent
    state["updated_at"] = int(time.time())
    atomic_json(STATE_PATH, state)


def resolve_user(client: XClient, handle: str, item: dict[str, Any]) -> str:
    if item.get("source_user_id"):
        return item["source_user_id"]
    payload = client.request(
        "GET",
        f"/users/by/username/{handle}",
        expected_cost=USER_READ,
        cost_label=f"resolve @{handle}",
    )
    item["source_user_id"] = payload["data"]["id"]
    return item["source_user_id"]


def fetch_following(
    client: XClient,
    handle: str,
    user_id: str,
    item: dict[str, Any],
    state: dict[str, Any],
) -> list[str]:
    roster_path = ROSTERS_DIR / f"{handle.lower()}.json"
    if item.get("roster_complete") and roster_path.exists():
        return load_json(roster_path, [])

    ids = list(dict.fromkeys(item.get("roster_ids", [])))
    token = item.get("following_next_token")
    first = not item.get("following_started")
    while first or token:
        first = False
        remaining = client.budget.limit - client.budget.spent
        max_results = max(1, min(1000, int(remaining / FOLLOWING_READ)))
        params: dict[str, Any] = {"max_results": max_results}
        if token:
            params["pagination_token"] = token
        payload = client.request(
            "GET",
            f"/users/{user_id}/following",
            params=params,
            expected_cost=max_results * FOLLOWING_READ,
            cost_label=f"read up to {max_results} follows for @{handle}",
        )
        page = [row["id"] for row in payload.get("data", [])]
        # X charges returned resources; refund unused reservation.
        client.budget.spent = round(
            client.budget.spent - (max_results - len(page)) * FOLLOWING_READ, 6
        )
        ids = list(dict.fromkeys(ids + page))
        token = payload.get("meta", {}).get("next_token")
        item.update(
            following_started=True,
            following_next_token=token,
            roster_ids=ids,
        )
        save_state(state, client.budget)

    item["roster_complete"] = True
    item["roster_count"] = len(ids)
    item.pop("roster_ids", None)
    item.pop("following_next_token", None)
    atomic_json(roster_path, ids)
    save_state(state, client.budget)
    return ids


def create_list(client: XClient, target: dict[str, Any], item: dict[str, Any]) -> str:
    list_id = item.get("list_id") or target.get("list_id")
    if list_id:
        item["list_id"] = list_id
        return list_id
    payload = client.request(
        "POST",
        "/lists",
        body={
            "name": target["list_name"],
            "private": True,
            "description": f"Accounts followed by @{target['handle']}.",
        },
        expected_cost=LIST_CREATE,
        cost_label=f"create {target['list_name']}",
        is_write=True,
    )
    item["list_id"] = payload["data"]["id"]
    return item["list_id"]


def fetch_existing_members(
    client: XClient,
    list_id: str,
    target: dict[str, Any],
    item: dict[str, Any],
    state: dict[str, Any],
) -> set[str]:
    if item.get("members_loaded"):
        return set(item.get("member_ids", []))
    if target.get("known_empty"):
        item["members_loaded"] = True
        item["member_ids"] = []
        return set()
    members: list[str] = []
    token: str | None = None
    while True:
        params: dict[str, Any] = {"max_results": 100}
        if token:
            params["pagination_token"] = token
        payload = client.request(
            "GET",
            f"/lists/{list_id}/members",
            params=params,
            expected_cost=100 * LIST_READ,
            cost_label=f"read current members of {target['list_name']}",
        )
        page = [row["id"] for row in payload.get("data", [])]
        client.budget.spent = round(
            client.budget.spent - (100 - len(page)) * LIST_READ, 6
        )
        members.extend(page)
        token = payload.get("meta", {}).get("next_token")
        if not token:
            break
    item["members_loaded"] = True
    item["member_ids"] = list(dict.fromkeys(members))
    save_state(state, client.budget)
    return set(item["member_ids"])


def add_members(
    client: XClient,
    target: dict[str, Any],
    list_id: str,
    roster: Iterable[str],
    existing: set[str],
    item: dict[str, Any],
    state: dict[str, Any],
    max_writes: int,
) -> int:
    writes = 0
    skipped = set(item.get("skipped_member_ids", []))
    for user_id in roster:
        if user_id in existing or user_id in skipped:
            continue
        if max_writes and writes >= max_writes:
            break
        try:
            payload = client.request(
                "POST",
                f"/lists/{list_id}/members",
                body={"user_id": user_id},
                expected_cost=LIST_MANAGE,
                cost_label=f"add member to {target['list_name']}",
                is_write=True,
            )
        except XAPIError as exc:
            if exc.status != 403:
                raise
            skipped.add(user_id)
            item["skipped_member_ids"] = sorted(skipped)
            save_state(state, client.budget)
            print(
                f"{target['name']}: skipped one account X would not allow",
                flush=True,
            )
            continue
        if not payload.get("data", {}).get("is_member"):
            raise RuntimeError(f"X did not confirm member {user_id} for list {list_id}")
        existing.add(user_id)
        item["member_ids"] = sorted(existing)
        writes += 1
        save_state(state, client.budget)
        if writes % 25 == 0:
            print(
                f"{target['name']}: {len(existing)}/{item['roster_count']} "
                f"(${client.budget.spent:.3f})",
                flush=True,
            )
    item["complete"] = len(existing | skipped) >= item["roster_count"]
    save_state(state, client.budget)
    return writes


def load_targets() -> list[dict[str, Any]]:
    targets = load_json(TARGETS_PATH, [])
    for target in targets:
        if len(target["list_name"]) > 25:
            raise RuntimeError(f"List name too long: {target['list_name']}")
    return targets


def cmd_plan() -> int:
    targets = load_targets()
    known = {
        "patrickc": 35,
        "agnescallard": 225,
        "lvcadeleo": 394,
        "tylercowen": 559,
        "gleech": 658,
        "amandaaskell": 663,
        "paulg": 800,
        "nabeelqu": 889,
        "karpathy": 1125,
    }
    existing = {"tylercowen": 64, "paulg": 39, "nabeelqu": 67}
    total = 0.0
    for target in targets:
        handle = target["handle"].lower()
        count = known[handle]
        current = existing.get(handle, 0)
        cost = (
            USER_READ
            + count * FOLLOWING_READ
            + (count - current) * LIST_MANAGE
            + current * LIST_READ
        )
        if not target.get("list_id"):
            cost += LIST_CREATE
        total += cost
        print(f"{target['name']:<18} {count:>5}  ${cost:>6.2f}")
    print(f"{'Projected total':<25} ${total:.2f}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    load_dotenv()
    state = load_json(STATE_PATH, {"version": 1, "targets": {}})
    budget = Budget(args.budget, float(state.get("estimated_spend_usd", 0.0)))
    client = XClient(budget, WriteLimiter(args.window_writes, args.window_seconds))
    remaining_writes = args.max_writes
    for target in load_targets():
        item = target_state(state, target["handle"])
        if item.get("complete"):
            print(f"{target['name']}: complete", flush=True)
            continue
        user_id = resolve_user(client, target["handle"], item)
        save_state(state, budget)
        roster = fetch_following(client, target["handle"], user_id, item, state)
        list_id = create_list(client, target, item)
        save_state(state, budget)
        existing = fetch_existing_members(client, list_id, target, item, state)
        allowed = remaining_writes if args.max_writes else 0
        used = add_members(client, target, list_id, roster, existing, item, state, allowed)
        if args.max_writes:
            remaining_writes -= used
            if remaining_writes <= 0:
                break
    print(json.dumps({"estimated_spend_usd": budget.spent, "state": str(STATE_PATH)}))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sync = sub.add_parser("sync")
    sync.add_argument("--budget", type=float, default=81.0)
    sync.add_argument("--max-writes", type=int, default=0)
    sync.add_argument("--window-writes", type=int, default=295)
    sync.add_argument("--window-seconds", type=int, default=900)
    return p


def main() -> None:
    args = parser().parse_args()
    try:
        code = cmd_plan() if args.command == "plan" else cmd_sync(args)
    except (RuntimeError, requests.RequestException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
