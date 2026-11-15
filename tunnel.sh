#!/usr/bin/env bash
# Market Eye tailnet address.
#
#   ./tunnel.sh start|stop|status|setup
#
# Publishes the local dev site inside the owner's Tailscale network as
#   https://marketeye.tail5bc03a.ts.net
# using a userspace Tailscale client kept in .run/ts (gitignored).
# Tailnet-only: not exposed to the public internet.
#
# `setup` downloads the client once; after that `start` is idempotent.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${MARKETEYE_PORT:-8767}"
TS_DIR="$ROOT/.run/ts"
TS_VERSION="1.104.7"
TS_ARCHIVE="tailscale_${TS_VERSION}_arm64.tgz"
DOMAIN="marketeye.tail5bc03a.ts.net"
SOCK="$TS_DIR/tailscaled.sock"
STATE_DIR="$TS_DIR/state"
STATE="$STATE_DIR/tailscaled.state"
PID_FILE="$TS_DIR/tailscaled.pid"
LOG="$TS_DIR/tailscaled.log"
URL="https://${DOMAIN}"

mkdir -p "$TS_DIR" "$STATE_DIR"
export TMPDIR="${TMPDIR:-$ROOT/.run/tmp}"
mkdir -p "$TMPDIR"

bin_dir() {
  find "$TS_DIR" -maxdepth 1 -type d -name "tailscale_${TS_VERSION}_*" | head -1
}

ts_bin() {
  local dir
  dir="$(bin_dir)"
  [[ -n "$dir" && -x "$dir/tailscale" ]] && echo "$dir/tailscale"
}

tailscaled_bin() {
  local dir
  dir="$(bin_dir)"
  [[ -n "$dir" && -x "$dir/tailscaled" ]] && echo "$dir/tailscaled"
}

setup() {
  if [[ -n "$(ts_bin)" ]]; then
    echo "tailscale client already present"
    return 0
  fi
  local arch
  case "$(uname -m)" in
    aarch64 | arm64) arch="arm64" ;;
    x86_64 | amd64) arch="amd64" ;;
    *)
      echo "unsupported architecture: $(uname -m)" >&2
      return 1
      ;;
  esac
  echo "downloading tailscale ${TS_VERSION} (${arch}) into .run/ts ..."
  curl -fL --retry 2 -o "$TS_DIR/tailscale.tgz" \
    "https://pkgs.tailscale.com/stable/tailscale_${TS_VERSION}_${arch}.tgz"
  tar xzf "$TS_DIR/tailscale.tgz" -C "$TS_DIR"
  rm -f "$TS_DIR/tailscale.tgz"
  echo "done"
}

running() {
  local ts
  ts="$(ts_bin)" || return 1
  "$ts" --socket="$SOCK" status >/dev/null 2>&1
}

start() {
  local ts
  ts="$(ts_bin)" || {
    echo "tailscale client missing; run: $0 setup" >&2
    return 1
  }

  if ! running; then
    local daemon
    daemon="$(tailscaled_bin)"
    echo "starting tailscaled (userspace) ..."
    nohup "$daemon" \
      --tun=userspace-networking \
      --state="$STATE" \
      --statedir="$STATE_DIR" \
      --socket="$SOCK" \
      --socks5-server=127.0.0.1:1055 \
      --no-logs-no-support \
      >>"$LOG" 2>&1 &
    echo $! >"$PID_FILE"
    for _ in $(seq 1 50); do
      running && break
      sleep 0.2
    done
    running || {
      echo "tailscaled did not come up; see .run/ts/tailscaled.log" >&2
      return 1
    }
  fi

  if ! "$ts" --socket="$SOCK" serve status 2>/dev/null | grep -q "$DOMAIN"; then
    echo "publishing $PORT on the tailnet ..."
    "$ts" --socket="$SOCK" serve --bg --https=443 "http://127.0.0.1:${PORT}" >/dev/null
  fi

  echo "tailnet address: $URL"
  echo "tailnet only; the public internet cannot reach it."
}

stop() {
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "tailscaled stopped"
  else
    echo "tailscaled not running"
  fi
  rm -f "$PID_FILE"
}

status() {
  local ts
  ts="$(ts_bin)" || {
    echo "tailscale client missing; run: $0 setup"
    return 1
  }
  "$ts" --socket="$SOCK" status 2>&1 | head -8 || true
  echo '---'
  "$ts" --socket="$SOCK" serve status 2>&1 | head -6 || true
}

case "${1:-status}" in
  setup) setup ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  *)
    echo "usage: $0 setup|start|stop|status" >&2
    exit 2
    ;;
esac
