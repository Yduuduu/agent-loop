#!/usr/bin/env bash
# 백엔드(uvicorn)와 프론트엔드(next dev)를 동시에 실행한다.
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo "Stopping servers..."
  kill 0
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/backend"
  source .venv/bin/activate
  uvicorn app.main:app --reload
) &

(
  cd "$ROOT_DIR/frontend"
  npm run dev
) &

wait
