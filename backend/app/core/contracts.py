"""Loads the JSON Schemas in /contracts and validates data against them.

The schemas are the single source of truth shared by all three tracks; nothing
here redefines them.
"""

import json
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.core.config import get_settings


class ContractError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class Contracts:
    def __init__(self, root: Path):
        self.root = root.resolve()
        resources = [
            (path.as_uri(), Resource.from_contents(json.loads(path.read_text())))
            for path in self.root.rglob("*.schema.json")
        ]
        self.schemas = Registry().with_resources(resources)
        self._validators: dict[str, Draft202012Validator] = {}

    @cached_property
    def event_registry(self) -> dict[str, Any]:
        return json.loads((self.root / "events" / "registry.json").read_text())

    def validator(self, schema_path: str) -> Draft202012Validator:
        """schema_path is relative to /contracts, e.g. 'auth/actor.schema.json'."""
        if schema_path not in self._validators:
            uri = (self.root / schema_path).as_uri()
            self.schemas.get_or_retrieve(uri)  # fail fast on a bad path
            self._validators[schema_path] = Draft202012Validator(
                {"$ref": uri}, registry=self.schemas, format_checker=FormatChecker()
            )
        return self._validators[schema_path]

    def validate(self, schema_path: str, instance: Any) -> None:
        errors = sorted(self.validator(schema_path).iter_errors(instance), key=lambda e: e.path)
        if errors:
            raise ContractError([f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors])

    def validate_event(self, event: dict[str, Any]) -> None:
        """Envelope, then registration and ownership, then the payload for that type."""
        self.validate("events/envelope.schema.json", event)
        event_type = event["event_type"]
        namespace = event_type.split(".", 1)[0]
        if namespace not in self.event_registry["namespaces"]:
            raise ContractError([f"event_type: unknown namespace '{namespace}'"])
        entry = self.event_registry["events"].get(event_type)
        if entry is None:
            raise ContractError([f"event_type: '{event_type}' is not registered in events/registry.json"])
        if event["event_version"] != entry["version"]:
            expected, got = entry["version"], event["event_version"]
            raise ContractError([f"event_version: '{event_type}' is at version {expected}, got {got}"])
        try:
            self.validate(f"events/{entry['payload']}", event["payload"])
        except ContractError as exc:
            raise ContractError([f"payload/{e}" for e in exc.errors]) from None


@lru_cache
def get_contracts() -> Contracts:
    return Contracts(get_settings().contracts_dir)
