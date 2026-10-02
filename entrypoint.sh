#!/bin/sh
set -e

PORT="${PORT:-8000}"

if [ -n "${INFISICAL_CLIENT_ID:-}" ] && [ -n "${INFISICAL_CLIENT_SECRET:-}" ]; then
  INFISICAL_TOKEN=$(infisical login --method=universal-auth \
    --client-id="$INFISICAL_CLIENT_ID" \
    --client-secret="$INFISICAL_CLIENT_SECRET" \
    --silent --plain)

  # Uma execução por pasta: o registry só enxerga /llm, /google e /service-urls, nunca banco ou cache.
  FLAGS="--token=$INFISICAL_TOKEN --projectId=2296d19c-5f3b-41e1-afa3-fcde39966a71 --env=${INFISICAL_ENV:-qa}"

  exec infisical run $FLAGS --path=/llm -- \
    infisical run $FLAGS --path=/google -- \
    infisical run $FLAGS --path=/service-urls -- \
    uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
