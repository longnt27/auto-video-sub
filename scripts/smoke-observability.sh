#!/bin/sh
set -eu

API_URL="${API_URL:-http://127.0.0.1:8000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3200}"
JAEGER_URL="${JAEGER_URL:-http://127.0.0.1:16686}"

curl --fail --silent --show-error "${PROMETHEUS_URL}/-/ready" >/dev/null
curl --fail --silent --show-error "${GRAFANA_URL}/api/health" >/dev/null
curl --fail --silent --show-error "${JAEGER_URL}/" >/dev/null

# Generate one bounded, non-sensitive API request so the telemetry pipeline has data.
curl --fail --silent --show-error "${API_URL}/health/live" >/dev/null

attempt=0
while [ "$attempt" -lt 12 ]; do
  response="$(curl --fail --silent --show-error \
    --get \
    --data-urlencode 'query=auto_video_sub_http_requests_total' \
    "${PROMETHEUS_URL}/api/v1/query")"
  if printf '%s' "$response" | grep -q '"result":\[' && \
     ! printf '%s' "$response" | grep -q '"result":\[\]'; then
    printf '%s\n' "observability smoke passed"
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 5
done

printf '%s\n' "observability smoke failed: API metrics did not reach Prometheus" >&2
exit 1
