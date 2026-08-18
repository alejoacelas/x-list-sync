import requests

from x_list_sync import (
    Budget,
    WriteLimiter,
    XAPIError,
    XClient,
    add_members,
    load_targets,
)


def test_budget_stops_before_overspend():
    budget = Budget(1.0, 0.99)
    try:
        budget.require(0.02, "test")
    except RuntimeError as exc:
        assert "Budget stop" in str(exc)
    else:
        raise AssertionError("budget should stop")


def test_write_limiter_spreads_requests_across_window(monkeypatch):
    clock = iter([0.0, 0.0, 0.0, 0.0, 0.0])
    sleeps = []
    monkeypatch.setattr("x_list_sync.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("x_list_sync.time.sleep", sleeps.append)
    limiter = WriteLimiter(limit=2, window_seconds=10)

    limiter.acquire()
    limiter.acquire()

    assert sleeps == [5.0]


def test_target_list_names_fit_x_limit():
    assert all(len(target["list_name"]) <= 25 for target in load_targets())


def test_selected_targets_end_at_karpathy():
    assert [target["handle"] for target in load_targets()] == [
        "patrickc",
        "AgnesCallard",
        "lvcadeleo",
        "tylercowen",
        "gleech",
        "AmandaAskell",
        "paulg",
        "nabeelqu",
        "karpathy",
    ]


def test_request_retries_connection_reset(monkeypatch):
    class Response:
        status_code = 200
        ok = True
        headers = {}

        def json(self):
            return {"data": {"ok": True}}

    responses = iter([requests.ConnectionError("reset"), Response()])

    class Session:
        def request(self, *args, **kwargs):
            result = next(responses)
            if isinstance(result, Exception):
                raise result
            return result

    client = XClient.__new__(XClient)
    client.session = Session()
    client.budget = Budget(1.0)
    client.limiter = None
    monkeypatch.setattr("x_list_sync.time.sleep", lambda _: None)

    result = client.request(
        "GET", "/test", expected_cost=0.01, cost_label="test"
    )

    assert result == {"data": {"ok": True}}
    assert client.budget.spent == 0.01


def test_rate_limit_reports_assigned_headers(monkeypatch, capsys):
    class Response:
        status_code = 429
        ok = False
        text = '{"title":"Too Many Requests"}'
        headers = {
            "x-rate-limit-limit": "50",
            "x-rate-limit-remaining": "0",
            "x-rate-limit-reset": "200",
            "retry-after": "100",
        }

    responses = iter([Response(), successful_response()])

    class Session:
        def request(self, *args, **kwargs):
            return next(responses)

    client = XClient.__new__(XClient)
    client.session = Session()
    client.budget = Budget(1.0)
    client.limiter = None
    monkeypatch.setattr("x_list_sync.time.time", lambda: 100)
    monkeypatch.setattr("x_list_sync.time.sleep", lambda _: None)

    client.request("GET", "/test", expected_cost=0.01, cost_label="test")

    output = capsys.readouterr().out
    assert "limit=50, remaining=0, reset=200" in output
    assert "retry-after=100" in output
    assert 'body={"title":"Too Many Requests"}' in output


def successful_response():
    class Response:
        status_code = 200
        ok = True
        headers = {}

        def json(self):
            return {"data": {"ok": True}}

    return Response()


def test_add_members_skips_forbidden_account(monkeypatch):
    class Client:
        budget = Budget(1.0)

        def request(self, *args, body, **kwargs):
            if body["user_id"] == "blocked":
                raise XAPIError("POST", "/lists/1/members", 403, "forbidden")
            return {"data": {"is_member": True}}

    monkeypatch.setattr("x_list_sync.save_state", lambda *args: None)
    item = {"roster_count": 2}

    writes = add_members(
        Client(),
        {"name": "Test", "list_name": "Test"},
        "1",
        ["blocked", "allowed"],
        set(),
        item,
        {},
        0,
    )

    assert writes == 1
    assert item["member_ids"] == ["allowed"]
    assert item["skipped_member_ids"] == ["blocked"]
    assert item["complete"] is True
