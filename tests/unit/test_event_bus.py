"""Testa EventBus pub/sub."""
import time, threading
from core.atena_event_bus import AtenaEventBus, EventType, Event

def test_emit_triggers_handler():
    bus = AtenaEventBus(persist=False)
    received = []
    bus.subscribe(EventType.CYCLE_START, lambda e: received.append(e))
    bus.emit(EventType.CYCLE_START, "test", {"topic": "X"})
    time.sleep(0.1)
    assert len(received) == 1
    assert received[0].payload["topic"] == "X"

def test_wildcard_receives_all():
    bus = AtenaEventBus(persist=False)
    all_events = []
    bus.subscribe(None, lambda e: all_events.append(e))
    bus.emit(EventType.BUILD_SUCCESS, "builder", {})
    bus.emit(EventType.TEST_FAIL,    "tester",  {})
    time.sleep(0.15)
    assert len(all_events) == 2

def test_unsubscribe():
    bus = AtenaEventBus(persist=False)
    calls = []
    fn = lambda e: calls.append(e)
    bus.subscribe(EventType.RLHF_FEEDBACK, fn)
    bus.emit(EventType.RLHF_FEEDBACK, "src", {})
    time.sleep(0.1)
    bus.unsubscribe(EventType.RLHF_FEEDBACK, fn)
    bus.emit(EventType.RLHF_FEEDBACK, "src", {})
    time.sleep(0.1)
    assert len(calls) == 1

def test_handler_exception_does_not_crash_bus():
    bus = AtenaEventBus(persist=False)
    def bad(e): raise RuntimeError("boom")
    bus.subscribe(EventType.CYCLE_END, bad)
    bus.emit(EventType.CYCLE_END, "test", {})  # não deve explodir
    time.sleep(0.1)

def test_event_has_id_and_ts():
    bus = AtenaEventBus(persist=False)
    event = bus.emit(EventType.CUSTOM, "test", {"x": 1})
    assert event.event_id is not None
    assert event.ts > 0
