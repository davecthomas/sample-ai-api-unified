"""Observability capture and the threaded call runner."""

import logging

import pytest

from sample_ai_api_unified import obs, runner


@pytest.fixture(autouse=True)
def clean_buffer():
    obs.install()
    obs.clear()
    yield
    obs.clear()


def test_observability_logger_lands_in_buffer():
    logging.getLogger(obs.OBSERVABILITY_LOGGERS[0]).info("ai_api_call_input {...}")
    assert any("ai_api_call_input" in line for line in obs.all_events())


def test_metrics_logger_lands_in_buffer():
    logging.getLogger(obs.OBSERVABILITY_LOGGERS[1]).info("middleware_execution_timing x=1")
    assert any("middleware_execution_timing" in line for line in obs.all_events())


def test_tail_returns_most_recent():
    logger = logging.getLogger(obs.OBSERVABILITY_LOGGERS[0])
    for index in range(20):
        logger.info("event %d", index)
    tail = obs.tail(5)
    assert len(tail) == 5
    assert "event 19" in tail[-1]


def test_install_is_idempotent():
    logger = logging.getLogger(obs.OBSERVABILITY_LOGGERS[0])
    handler_count = len(logger.handlers)
    obs.install()
    obs.install()
    assert len(logger.handlers) == handler_count


def test_run_call_returns_result():
    assert runner.run_call("adding", lambda: 2 + 3) == 5


def test_run_call_reraises_worker_exception():
    def boom():
        raise ValueError("worker failed")

    with pytest.raises(ValueError, match="worker failed"):
        runner.run_call("failing", boom)


def test_run_call_reports_new_events(capsys):
    def emits():
        logging.getLogger(obs.OBSERVABILITY_LOGGERS[0]).info("ai_api_call_output {...}")
        return "done"

    assert runner.run_call("emitting", emits) == "done"
    assert "Observability events" in capsys.readouterr().out


def test_events_since_survives_buffer_wraparound():
    logger = logging.getLogger(obs.OBSERVABILITY_LOGGERS[0])
    for index in range(obs._BUFFER.maxlen + 10):  # fill past capacity
        logger.info("warmup %d", index)
    marker = obs.event_count()
    logger.info("fresh event")
    new_events = obs.events_since(marker)
    assert len(new_events) == 1
    assert "fresh event" in new_events[0]


def test_events_since_empty_when_nothing_new():
    marker = obs.event_count()
    assert obs.events_since(marker) == []
