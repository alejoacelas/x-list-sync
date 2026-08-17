from x_list_sync import Budget, load_targets


def test_budget_stops_before_overspend():
    budget = Budget(1.0, 0.99)
    try:
        budget.require(0.02, "test")
    except RuntimeError as exc:
        assert "Budget stop" in str(exc)
    else:
        raise AssertionError("budget should stop")


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

