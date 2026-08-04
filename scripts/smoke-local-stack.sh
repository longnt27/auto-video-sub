#!/bin/sh
set -eu

web_url=${APP_BASE_URL:-http://127.0.0.1:3100}
api_url=${API_BASE_URL:-http://127.0.0.1:8000}

curl --fail --silent --show-error "${web_url}/api/health"
printf '\n'
curl --fail --silent --show-error "${api_url}/health/ready"
printf '\n'
