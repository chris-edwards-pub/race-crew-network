#!/usr/bin/env bash
set -euo pipefail

# ── Local development helper ──────────────────────────────────────────
# Usage: ./dev.sh {start|stop|restart|reset-db|status|cleanup|logs}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${DEV_PORT:-5001}"
PID_FILE=".flask.pid"
LOG_FILE=".dev.log"
VENV_DIR=".venv"
DB_NAME="racecrew"
DB_URL="mysql+pymysql://root@localhost:3306/${DB_NAME}"

# ── Colors ────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

# ── Helpers ───────────────────────────────────────────────────────────
load_env() {
    if [[ -f .env ]]; then
        set -a
        source .env
        set +a
    else
        red "No .env file found. Copy .env.example to .env and fill in values."
        exit 1
    fi
    # Override DATABASE_URL for local MySQL (root, no password)
    export DATABASE_URL="$DB_URL"
}

activate_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        yellow "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
}

is_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    # Also check if something is on the port
    if lsof -ti :"$PORT" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

ensure_db() {
    if mysql -u root -e "SELECT 1 FROM ${DB_NAME}.users LIMIT 1" >/dev/null 2>&1; then
        return 0
    fi
    yellow "Creating database ${DB_NAME}..."
    mysql -u root -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME};"
}

# ── Commands ──────────────────────────────────────────────────────────
cmd_start() {
    if is_running; then
        yellow "Flask is already running on port ${PORT}."
        yellow "Use './dev.sh logs' to view output or './dev.sh restart' to restart."
        return 0
    fi

    load_env
    activate_venv

    yellow "Installing dependencies..."
    pip install -q -r requirements.txt

    ensure_db

    yellow "Running migrations..."
    flask db upgrade

    yellow "Ensuring admin account exists..."
    flask init-admin 2>&1 || true

    yellow "Starting Flask on port ${PORT}..."
    flask run --port "$PORT" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"

    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        green "Flask running at http://localhost:${PORT} (PID ${pid})"
        green "Login: ${INIT_ADMIN_EMAIL:-admin@racecrew.net}"
    else
        red "Flask failed to start. Check logs:"
        tail -20 "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

cmd_stop() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            green "Stopped Flask (PID ${pid})."
        fi
        rm -f "$PID_FILE"
    fi
    # Kill anything else on the port
    local pids
    pids=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        green "Killed process(es) on port ${PORT}."
    fi
    if ! is_running; then
        green "Flask is stopped."
    fi
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_reset_db() {
    cmd_stop

    yellow "Dropping database ${DB_NAME}..."
    mysql -u root -e "DROP DATABASE IF EXISTS ${DB_NAME};"
    mysql -u root -e "CREATE DATABASE ${DB_NAME};"
    green "Database recreated."

    load_env
    activate_venv

    yellow "Running migrations..."
    flask db upgrade

    yellow "Creating admin account..."
    flask init-admin
    green "Database reset complete."
}

cmd_status() {
    if is_running; then
        local pid=""
        [[ -f "$PID_FILE" ]] && pid=$(cat "$PID_FILE")
        green "Flask is running on port ${PORT}${pid:+ (PID ${pid})}."
    else
        yellow "Flask is not running."
    fi

    if mysql -u root -e "SELECT COUNT(*) AS regattas FROM ${DB_NAME}.regattas;" 2>/dev/null; then
        green "Database ${DB_NAME} is accessible."
    else
        yellow "Database ${DB_NAME} is not accessible or does not exist."
    fi
}

cmd_cleanup() {
    red "This will stop the server, drop the database, and remove .venv."
    read -rp "Are you sure? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        yellow "Cancelled."
        return 0
    fi

    cmd_stop

    yellow "Dropping database ${DB_NAME}..."
    mysql -u root -e "DROP DATABASE IF EXISTS ${DB_NAME};" 2>/dev/null || true
    green "Database dropped."

    if [[ -d "$VENV_DIR" ]]; then
        yellow "Removing ${VENV_DIR}..."
        rm -rf "$VENV_DIR"
        green "Virtual environment removed."
    fi

    rm -f "$LOG_FILE" "$PID_FILE"
    green "Cleanup complete."
}

cmd_logs() {
    if [[ -f "$LOG_FILE" ]]; then
        tail -f "$LOG_FILE"
    else
        yellow "No log file found. Is Flask running?"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────
case "${1:-}" in
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    restart)  cmd_restart ;;
    reset-db) cmd_reset_db ;;
    status)   cmd_status ;;
    cleanup)  cmd_cleanup ;;
    logs)     cmd_logs ;;
    *)
        echo "Usage: ./dev.sh {start|stop|restart|reset-db|status|cleanup|logs}"
        echo ""
        echo "Commands:"
        echo "  start      Install deps, migrate DB, start Flask on port ${PORT}"
        echo "  stop       Stop Flask server"
        echo "  restart    Stop then start"
        echo "  reset-db   Drop DB, recreate, migrate, create admin"
        echo "  status     Check if Flask is running and DB is accessible"
        echo "  cleanup    Full teardown (stop, drop DB, remove .venv)"
        echo "  logs       Tail Flask output"
        exit 1
        ;;
esac
