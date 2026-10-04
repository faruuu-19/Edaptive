#!/usr/bin/env bash
# Regenerates typed models from /contracts. Never edit generated files by hand.
#   backend/app/contracts/generated/  (Pydantic v2)
#   frontend/src/contracts/generated/ (TypeScript)
# CI runs this and fails if the output differs from what is committed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Only *.schema.json files are schemas (examples/ and registry.json are not).
(cd "$ROOT/contracts" && find . -name '*.schema.json' -exec rsync -R {} "$STAGE/" \;)

PY_OUT="$ROOT/backend/app/contracts/generated"
rm -rf "$PY_OUT"
(cd "$ROOT/backend" && uv run --quiet datamodel-codegen \
  --input "$STAGE" --input-file-type jsonschema \
  --output "$PY_OUT" --output-model-type pydantic_v2.BaseModel \
  --use-annotated --field-constraints --use-title-as-name --use-double-quotes \
  --target-python-version 3.12 --disable-timestamp --formatters ruff-format \
  --custom-file-header "# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.")

TS_OUT="$ROOT/frontend/src/contracts/generated"
rm -rf "$TS_OUT"
(cd "$ROOT/frontend" && node scripts/gen-contracts.mjs "$ROOT/contracts" "$TS_OUT")
echo "contracts regenerated"
