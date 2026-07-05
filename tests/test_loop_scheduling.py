import main


def test_due_for_jobs_check_false_before_interval_elapsed():
    assert main.due_for_jobs_check(last_jobs_run=1000, now=1000 + main.JOBS_CHECK_INTERVAL - 1) is False


def test_due_for_jobs_check_true_once_interval_elapsed():
    assert main.due_for_jobs_check(last_jobs_run=1000, now=1000 + main.JOBS_CHECK_INTERVAL) is True


def test_run_loop_iteration_always_checks_messages(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "check_incoming_messages", lambda start_time: calls.append("messages"))
    monkeypatch.setattr(main, "check_jobs", lambda: calls.append("jobs"))

    main.run_loop_iteration(last_jobs_run=0, now=1)

    assert "messages" in calls


def test_run_loop_iteration_skips_jobs_before_interval_elapsed(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "check_incoming_messages", lambda start_time: None)
    monkeypatch.setattr(main, "check_jobs", lambda: calls.append("jobs"))

    last_jobs_run = 1000
    result = main.run_loop_iteration(last_jobs_run, now=1000 + main.JOBS_CHECK_INTERVAL - 1)

    assert calls == []
    assert result == last_jobs_run


def test_run_loop_iteration_runs_jobs_once_interval_elapsed(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "check_incoming_messages", lambda start_time: None)
    monkeypatch.setattr(main, "check_jobs", lambda: calls.append("jobs"))

    now = 1000 + main.JOBS_CHECK_INTERVAL
    result = main.run_loop_iteration(last_jobs_run=1000, now=now)

    assert calls == ["jobs"]
    assert result == now


def test_run_loop_iteration_runs_jobs_immediately_on_first_call(monkeypatch):
    # last_jobs_run starts at 0 in main.py, so on the very first iteration
    # (now being a real, large epoch timestamp) a jobs check always fires.
    calls = []
    monkeypatch.setattr(main, "check_incoming_messages", lambda start_time: None)
    monkeypatch.setattr(main, "check_jobs", lambda: calls.append("jobs"))

    main.run_loop_iteration(last_jobs_run=0, now=1_700_000_000)

    assert calls == ["jobs"]
