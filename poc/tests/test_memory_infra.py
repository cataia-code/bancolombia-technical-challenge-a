"""Tests for in-memory infrastructure helpers."""
import json

from infra.memory import InMemoryTracer, RealSleeper


def test_prints_structured_log_when_echo_is_enabled(capsys):
    tracer = InMemoryTracer(echo=True)

    tracer.emit("EVENT", "cid-log", {"status": "OK"})

    assert tracer.events == [{"event": "EVENT", "correlationId": "cid-log", "status": "OK"}]
    assert json.loads(capsys.readouterr().err) == {
        "event": "EVENT",
        "correlationId": "cid-log",
        "status": "OK",
    }


def test_real_sleeper_delegates_to_time_sleep(monkeypatch):
    captured = {}

    def fake_sleep(seconds):
        captured["seconds"] = seconds

    monkeypatch.setattr("time.sleep", fake_sleep)

    RealSleeper().sleep(0.25)

    assert captured == {"seconds": 0.25}
