#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
API_PREFIX="${API_PREFIX:-/api}"

log() {
  printf '[smoke] %s\n' "$1"
}

fail() {
  printf '[smoke] ERROR: %s\n' "$1" >&2
  exit 1
}

require_contains() {
  local label="$1"
  local body="$2"
  local expected="$3"

  if [[ "$body" != *"$expected"* ]]; then
    fail "$label did not contain expected text: $expected"
  fi
}

request() {
  local method="$1"
  local url="$2"
  local data="${3:-}"

  if [[ -n "$data" ]]; then
    curl -sS -X "$method" \
      -H 'Content-Type: application/json' \
      -d "$data" \
      "$url"
  else
    curl -sS -X "$method" "$url"
  fi
}

log "Checking API health at $API_BASE_URL/health"
health_response="$(request GET "$API_BASE_URL/health")"
require_contains "health response" "$health_response" '"status":"ok"'

log "Checking API readiness at $API_BASE_URL/health/ready"
ready_response="$(request GET "$API_BASE_URL/health/ready")"
require_contains "readiness response" "$ready_response" '"ready":true'

log "Checking clean reindex endpoint"
reindex_response="$(request POST "$API_BASE_URL$API_PREFIX/documents/reindex")"
require_contains "reindex response" "$reindex_response" '"documents_ingested"'

log "Checking legal search endpoint"
legal_response="$(request GET "$API_BASE_URL$API_PREFIX/legal/search?q=Dieu30&top_k=3")"
require_contains "legal search response" "$legal_response" '"results"'

log "Checking chat query endpoint"
chat_response="$(request POST "$API_BASE_URL$API_PREFIX/chat/query" '{"question":"bao nhiêu tuổi thì phải đi nghĩa vụ quân sự?","top_k":3}')"
require_contains "chat response" "$chat_response" '"conversation_id"'
require_contains "chat response" "$chat_response" '"citations"'
require_contains "chat response" "$chat_response" '"answer"'
require_contains "chat response" "$chat_response" 'đủ 18 tuổi'

log "Smoke test passed"
