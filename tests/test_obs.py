"""Observability event capture."""

import logging

import pytest

from sample_ai_api_unified import obs


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
