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


def test_cost_topic_lands_in_buffer():
    # Library 2.10.0 cost enrichment logs ai_api_call_cost on its own topic.
    logging.getLogger("ai_api_unified.observability.cost").info("ai_api_call_cost {usd: 0.0007}")
    assert any("ai_api_call_cost" in line for line in obs.all_events())


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


def test_enable_file_logging_writes_events_to_a_dated_file(tmp_path):
    obs._file_handler = None  # reset the module-level guard for the test
    try:
        log_path = obs.enable_file_logging(tmp_path)
        assert log_path.parent == tmp_path
        assert log_path.name.startswith("observability-")
        logging.getLogger(obs.OBSERVABILITY_LOGGERS[0]).info("ai_api_call_input {sample}")
        obs._file_handler.flush()
        contents = log_path.read_text()
        assert "ai_api_call_input" in contents
        assert "File logging enabled" in contents  # startup marker recorded too
    finally:
        if obs._file_handler is not None:
            for name in obs._FILE_LOGGERS:
                logging.getLogger(name).removeHandler(obs._file_handler)
            obs._file_handler.close()
            obs._file_handler = None


def test_enable_file_logging_is_idempotent(tmp_path):
    obs._file_handler = None
    try:
        first = obs.enable_file_logging(tmp_path)
        second = obs.enable_file_logging(tmp_path)
        assert first == second
        # Only one handler was attached despite two calls.
        logger = logging.getLogger(obs.OBSERVABILITY_LOGGERS[0])
        assert logger.handlers.count(obs._file_handler) == 1
    finally:
        if obs._file_handler is not None:
            for name in obs._FILE_LOGGERS:
                logging.getLogger(name).removeHandler(obs._file_handler)
            obs._file_handler.close()
            obs._file_handler = None
