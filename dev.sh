#!/usr/bin/env bash
# MarketEye dev runner.
#
#   ./dev.sh start | stop | restart | status
#
# Serves the static front-end on port 8767 (docflow keeps 8765).
# No dependencies: the server is plain Python stdlib.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${MARKETEYE_PORT:-8767}"
RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/server.pid"
LOG_FILE="$RUN_DIR/server.log"
URL="http://127.0.0.1:${PORT}/"

mkdir -p "$RUN_DIR"

is_up() {
  curl -fsS --max-time 2 "${URL}healthz" >/dev/null 2>&1
}

read_pid() {
  [[ -f "$PID_FILE" ]] && cat "$PID_FILE" 2>/dev/null || true
}

start() {
  if is_up; then
    echo "already running: $URL"
    return 0
  fi

  local pid
  pid="$(read_pid)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "stale process $pid is not answering; restarting"
    stop >/dev/null 2>&1 || true
  fi

  rm -f "$PID_FILE"
  nohup python3 "$ROOT/dev_server.py" "$PORT" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"

  for _ in $(seq 1 50); do
    if is_up; then
      echo "started: $URL (pid $(read_pid), log .run/server.log)"
      return 0
    fi
    sleep 0.1
  done

  echo "failed to start; see .run/server.log" >&2
  return 1
}

stop() {
  local pid
  pid="$(read_pid)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
    kill -9 "$pid" 2>/dev/null || true
    echo "stopped: $URL"
  else
    echo "not running"
  fi
  rm -f "$PID_FILE"
}

status() {
  if is_up; then
    echo "running: $URL"
  else
    echo "not running"
    return 1
  fi
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) stop >/dev/null 2>&1 || true; start ;;
  status) status ;;
  *)
    echo "usage: $0 start|stop|restart|status" >&2
    exit 2
    ;;
esac
