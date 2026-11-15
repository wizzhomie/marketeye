#!/usr/bin/env bash
# MarketEye daily runner.
#
#   ./daily.sh run      one check now (digest printed and saved)
#   ./daily.sh start    background scheduler: one check a day
#   ./daily.sh stop     stop the scheduler
#   ./daily.sh status   is the scheduler running?
#   ./daily.sh show     print the latest saved digest
#   ./daily.sh log      last lines of the scheduler log
#
# The scheduler checks every 30 seconds whether the configured local time
# (MARKETEYE_DAILY_AT, default 09:00) has passed and has not been handled yet
# today, then runs one daily pass: fetch every live source, store the readings,
# advance the demo shop and write data/digests/YYYY-MM-DD.txt.
#
# Needs the project virtualenv: see "Run it" in README.md.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/daily.pid"
LOG_FILE="$RUN_DIR/daily.log"
PYTHON="$ROOT/.venv/bin/python"
AT="${MARKETEYE_DAILY_AT:-09:00}"

mkdir -p "$RUN_DIR"

read_pid() {
  [[ -f "$PID_FILE" ]] && cat "$PID_FILE" 2>/dev/null || true
}

is_running() {
  local pid
  pid="$(read_pid)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

run_once() {
  if [[ ! -x "$PYTHON" ]]; then
    echo "missing virtualenv: run python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    return 1
  fi
  exec "$PYTHON" "$ROOT/daily.py" run
}

start() {
  if is_running; then
    echo "already running: daily check at $AT (pid $(read_pid))"
    return 0
  fi

  if [[ ! -x "$PYTHON" ]]; then
    echo "missing virtualenv: run python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    return 1
  fi

  rm -f "$PID_FILE"
  MARKETEYE_DAILY_AT="$AT" nohup "$PYTHON" "$ROOT/daily.py" loop >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"

  for _ in $(seq 1 30); do
    if is_running; then
      echo "started: daily check at $AT (pid $(read_pid), log .run/daily.log)"
      return 0
    fi
    sleep 0.1
  done

  echo "failed to start; see .run/daily.log" >&2
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
    echo "stopped: daily check"
  else
    echo "not running"
  fi
  rm -f "$PID_FILE"
}

status() {
  if is_running; then
    echo "running: daily check at $AT (pid $(read_pid))"
    return 0
  fi
  echo "not running: daily check at $AT"
  return 1
}

case "${1:-status}" in
  run) run_once ;;
  start) start ;;
  stop) stop ;;
  restart) stop >/dev/null 2>&1 || true; start ;;
  status) status ;;
  show)
    if [[ ! -x "$PYTHON" ]]; then
      echo "missing virtualenv" >&2
      exit 1
    fi
    exec "$PYTHON" "$ROOT/daily.py" show
    ;;
  log)
    [[ -f "$LOG_FILE" ]] && tail -n 40 "$LOG_FILE" || echo "no log yet: .run/daily.log"
    ;;
  *)
    echo "usage: $0 run|start|stop|restart|status|show|log" >&2
    exit 2
    ;;
esac
