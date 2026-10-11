"""Every schema loads, every example matches its schema, and the event registry is consistent.
If one of these fails, a contract change broke something another track relies on."""

import json
from pathlib import Path

import pytest

from app.core.contracts import ContractError, get_contracts

contracts = get_contracts()
ROOT = contracts.root
EXAMPLES = ROOT / "examples"

EXAMPLE_SCHEMAS = {
    "auth": "auth/actor.schema.json",
    "curriculum": "curriculum/node.schema.json",
}


@pytest.mark.parametrize("path", sorted(ROOT.rglob("*.schema.json")), ids=lambda p: str(p.relative_to(ROOT)))
def test_schema_is_valid_json_schema(path: Path):
    contracts.validator(str(path.relative_to(ROOT))).check_schema(json.loads(path.read_text()))


@pytest.mark.parametrize("path", sorted((EXAMPLES / "events").glob("*.json")), ids=lambda p: p.name)
def test_event_examples_are_valid(path: Path):
    contracts.validate_event(json.loads(path.read_text()))


@pytest.mark.parametrize(
    "path",
    [p for folder in EXAMPLE_SCHEMAS for p in sorted((EXAMPLES / folder).glob("*.json"))],
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_examples_are_valid(path: Path):
    contracts.validate(EXAMPLE_SCHEMAS[path.parent.name], json.loads(path.read_text()))


def test_registry_entries_are_consistent():
    registry = contracts.event_registry
    for event_type, entry in registry["events"].items():
        assert event_type.split(".")[0] in registry["namespaces"], f"{event_type}: namespace not owned"
        payload = ROOT / "events" / entry["payload"]
        assert payload.exists(), f"{event_type}: missing {payload}"
        assert payload.name.endswith(f".v{entry['version']}.schema.json"), f"{event_type}: version mismatch"


def test_every_payload_schema_is_registered():
    registered = {e["payload"] for e in contracts.event_registry["events"].values()}
    on_disk = {str(p.relative_to(ROOT / "events")) for p in (ROOT / "events" / "payloads").glob("*.json")}
    assert on_disk <= registered, f"unregistered payload schemas: {on_disk - registered}"


def _event(**overrides):
    event = json.loads((EXAMPLES / "events" / "session.started.json").read_text())
    event.update(overrides)
    return event


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"event_type": "session.paused"}, "not registered"),
        ({"event_type": "homework.started"}, "unknown namespace"),
        ({"event_version": 2}, "version 1"),
        ({"payload": {"entry": "whenever"}}, "payload/entry"),
        ({"payload": {"entry": "scheduled", "extra": 1}}, "payload"),
        ({"event_id": "not-a-uuid"}, "event_id"),
        ({"occurred_at": "yesterday"}, "occurred_at"),
        ({"unexpected": True}, "Additional properties"),
    ],
)
def test_bad_events_are_rejected(bad, message):
    with pytest.raises(ContractError, match=message):
        contracts.validate_event(_event(**bad))
