#!/usr/bin/env bash
# Regenerates the frontend's TypeScript types from /contracts. Never edit generated files by hand.
# (The backend validates against the JSON Schemas directly, so it needs no generated code.)
# `make check` fails if the committed output is stale.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TS_OUT="$ROOT/frontend/src/contracts/generated"
rm -rf "$TS_OUT"
(cd "$ROOT/frontend" && node scripts/gen-contracts.mjs "$ROOT/contracts" "$TS_OUT")
echo "contracts regenerated"
