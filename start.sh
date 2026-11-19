#!/usr/bin/env bash
# ==============================================================================
# MassCommAI — End-to-End Application Startup & Process Management Script
# ==============================================================================
# Usage:
#   ./start.sh            Start with existing local PostgreSQL and Redis
#   ./start.sh --docker   Start/reuse PostgreSQL and Redis via Docker Compose
#   ./start.sh --status   Check status of application services and processes
#   ./start.sh --stop     Stop backend and frontend processes launched by this script
#   ./start.sh --help     Display usage instructions
# ==============================================================================

set -eo pipefail

# Resolve repository root directory reliably regardless of caller working directory
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
REPO_ROOT="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

# Directory & File Constants
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
RUNTIME_DIR="$REPO_ROOT/.runtime"
LOGS_DIR="$REPO_ROOT/logs"

BACKEND_PID_FILE="$RUNTIME_DIR/backend.pid"
FRONTEND_PID_FILE="$RUNTIME_DIR/frontend.pid"
MASTER_PID_FILE="$RUNTIME_DIR/start.pid"
STOP_FLAG_FILE="$RUNTIME_DIR/stop.requested"
BACKEND_LOG="$LOGS_DIR/backend.log"
FRONTEND_LOG="$LOGS_DIR/frontend.log"

# Default Ports & Hosts
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="${PORT:-8000}"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="5173"

# Styling & Terminal formatting
if [ -t 1 ]; then
    BOLD="\033[1m"
    GREEN="\033[0;32m"
    BLUE="\033[0;34m"
    YELLOW="\033[1;33m"
    RED="\033[0;31m"
    CYAN="\033[0;36m"
    NC="\033[0m"
else
    BOLD=""
    GREEN=""
    BLUE=""
    YELLOW=""
    RED=""
    CYAN=""
    NC=""
fi

# Print banner helper
print_banner() {
    echo -e "${BOLD}${BLUE}==================================================${NC}"
    echo -e "${BOLD}${CYAN}            MASSCOMMAI APPLICATION                ${NC}"
    echo -e "${BOLD}${BLUE}==================================================${NC}"
}

# Print help message
show_help() {
    print_banner
    echo -e "${BOLD}MassCommAI Application Startup Utility${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo "  ./start.sh [OPTIONS]"
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo "  (no args)      Start application using available local PostgreSQL and Redis"
    echo "  --docker       Start/reuse PostgreSQL and Redis via Docker Compose, then start application"
    echo "  --status       Display backend, frontend, database, Redis, and PID status"
    echo "  --stop         Stop only backend and frontend processes launched by this script"
    echo "  --help, -h     Display this help message"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  ./start.sh            # Normal local startup"
    echo "  ./start.sh --docker   # Start with Docker-backed database and Redis"
    echo "  ./start.sh --status   # Check running status"
    echo "  ./start.sh --stop     # Stop running application"
    echo ""
    echo -e "${BOLD}Log files:${NC}"
    echo "  Backend        : logs/backend.log"
    echo "  Frontend       : logs/frontend.log"
    echo ""
    echo -e "${BOLD}Demo Seed Data:${NC}"
    echo "  To seed initial civic demo data separately when required:"
    echo "    python -m app.db.seed_demo   (from backend/ directory)"
    echo -e "${BOLD}${BLUE}==================================================${NC}"
}

# Verify if a given PID is alive and matches an expected process name keyword
is_pid_valid() {
    local pid="$1"
    local expected_pattern="$2"

    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1

    local cmd=""
    if ps -ww -p "$pid" -o args= >/dev/null 2>&1; then
        cmd=$(ps -ww -p "$pid" -o args= 2>/dev/null || true)
    elif ps -p "$pid" -o args= >/dev/null 2>&1; then
        cmd=$(ps -p "$pid" -o args= 2>/dev/null || true)
    elif ps -p "$pid" -o command= >/dev/null 2>&1; then
        cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
    fi

    if [ -n "$expected_pattern" ]; then
        if echo "$cmd" | grep -qE "$expected_pattern"; then
            return 0
        else
            return 1
        fi
    fi
    return 0
}

# Recursively collect all descendant PIDs of a process
get_descendants() {
    local parent="$1"
    local children
    children=$(pgrep -P "$parent" 2>/dev/null || true)
    for c in $children; do
        get_descendants "$c"
        echo "$c"
    done
}

# Terminate a PID and its child processes gracefully
stop_process() {
    local pid="$1"
    local name="$2"

    [ -n "$pid" ] || return 0
    if ! kill -0 "$pid" 2>/dev/null; then
        return 0
    fi

    printf "Stopping %s (PID: %s)... " "$name" "$pid"

    # Capture all descendant processes (e.g. npm -> node/vite, uvicorn -> reload worker)
    local descendants=""
    if command -v pgrep >/dev/null 2>&1; then
        descendants=$(get_descendants "$pid" || true)
    fi

    # Send SIGTERM first
    for d in $descendants; do
        kill -TERM "$d" 2>/dev/null || true
    done
    kill -TERM "$pid" 2>/dev/null || true

    # Wait up to 5 seconds for graceful shutdown
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 10 ]; do
        sleep 0.5
        waited=$((waited + 1))
    done

    # Force kill with SIGKILL if still running
    for d in $descendants; do
        if kill -0 "$d" 2>/dev/null; then
            kill -KILL "$d" 2>/dev/null || true
        fi
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null || true
    fi

    echo -e "${GREEN}Stopped.${NC}"
}

# Check status of application, database, and background processes
check_status() {
    print_banner
    echo -e "${BOLD}SERVICE AND PROCESS STATUS:${NC}"
    echo ""

    # Check Backend PID
    local b_running=0
    local b_pid=""
    if [ -f "$BACKEND_PID_FILE" ]; then
        b_pid=$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)
        if is_pid_valid "$b_pid" "uvicorn|python"; then
            b_running=1
        else
            echo -e "Backend PID File : ${YELLOW}Stale ($b_pid not running; cleaning up)${NC}"
            rm -f "$BACKEND_PID_FILE"
            b_pid=""
        fi
    fi

    if [ "$b_running" -eq 1 ]; then
        local health_status="Unresponsive"
        if curl -s -f "http://$BACKEND_HOST:$BACKEND_PORT/health" >/dev/null 2>&1; then
            health_status="Healthy (HTTP 200)"
        fi
        echo -e "Backend API      : ${GREEN}Running${NC} (PID: ${BOLD}$b_pid${NC}, Health: ${GREEN}$health_status${NC})"
        echo -e "                   URL: http://$BACKEND_HOST:$BACKEND_PORT"
        echo -e "                   Docs: http://$BACKEND_HOST:$BACKEND_PORT/docs"
    else
        echo -e "Backend API      : ${RED}Stopped${NC}"
    fi

    # Check Frontend PID
    local f_running=0
    local f_pid=""
    if [ -f "$FRONTEND_PID_FILE" ]; then
        f_pid=$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)
        if is_pid_valid "$f_pid" "vite|npm|node"; then
            f_running=1
        else
            echo -e "Frontend PID File: ${YELLOW}Stale ($f_pid not running; cleaning up)${NC}"
            rm -f "$FRONTEND_PID_FILE"
            f_pid=""
        fi
    fi

    if [ "$f_running" -eq 1 ]; then
        local f_status="Responding (HTTP 200)"
        if ! curl -s -f "http://$FRONTEND_HOST:$FRONTEND_PORT" >/dev/null 2>&1; then
            f_status="Starting / Compiling"
        fi
        echo -e "Frontend UI      : ${GREEN}Running${NC} (PID: ${BOLD}$f_pid${NC}, Status: ${GREEN}$f_status${NC})"
        echo -e "                   URL: http://$FRONTEND_HOST:$FRONTEND_PORT"
    else
        echo -e "Frontend UI      : ${RED}Stopped${NC}"
    fi

    echo ""
    echo -e "${BOLD}INFRASTRUCTURE SERVICES:${NC}"

    # Check Python environment
    detect_python_env >/dev/null 2>&1 || true
    if [ -n "$PYTHON_BIN" ] && [ -x "$PYTHON_BIN" ]; then
        # Check PostgreSQL
        if check_postgres_connected; then
            echo -e "PostgreSQL       : ${GREEN}Connected${NC} (Accepting queries)"
        else
            echo -e "PostgreSQL       : ${RED}Disconnected${NC} (Unreachable at configured DATABASE_URL)"
        fi

        # Check Redis
        if check_redis_connected; then
            echo -e "Redis            : ${GREEN}Connected${NC} (127.0.0.1:6379)"
        else
            echo -e "Redis            : ${YELLOW}Not Connected${NC} (In-memory rate limiter fallback active)"
        fi

        # Check Alembic Migration Revision
        local alembic_rev=""
        alembic_rev=$(cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -m alembic current 2>/dev/null | grep -E "^[a-f0-9]+" | head -n 1 || true)
        if [ -n "$alembic_rev" ]; then
            echo -e "Alembic Database : ${GREEN}Up to date${NC} (Revision: ${BOLD}$alembic_rev${NC})"
        else
            echo -e "Alembic Database : ${YELLOW}Status unverified${NC}"
        fi
    else
        echo -e "PostgreSQL       : ${YELLOW}Unknown${NC} (Python runtime not configured)"
        echo -e "Redis            : ${YELLOW}Unknown${NC} (Python runtime not configured)"
    fi

    echo ""
    echo -e "${BOLD}LOGS & RUNTIME:${NC}"
    echo "  Backend Log    : $BACKEND_LOG"
    echo "  Frontend Log   : $FRONTEND_LOG"
    echo -e "${BOLD}${BLUE}==================================================${NC}"
}

# Stop backend and frontend processes launched by start.sh
stop_application() {
    print_banner
    echo -e "${BOLD}Stopping MassCommAI application processes...${NC}"
    local stopped_any=0

    # Signal monitor loop that shutdown is intentional
    mkdir -p "$RUNTIME_DIR"
    touch "$STOP_FLAG_FILE"

    if [ -f "$FRONTEND_PID_FILE" ]; then
        local f_pid
        f_pid=$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)
        if [ -n "$f_pid" ] && is_pid_valid "$f_pid" "vite|npm|node"; then
            stop_process "$f_pid" "Frontend"
            stopped_any=1
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi

    if [ -f "$BACKEND_PID_FILE" ]; then
        local b_pid
        b_pid=$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)
        if [ -n "$b_pid" ] && is_pid_valid "$b_pid" "uvicorn|python"; then
            stop_process "$b_pid" "Backend"
            stopped_any=1
        fi
        rm -f "$BACKEND_PID_FILE"
    fi

    # Terminate master start.sh process if running
    if [ -f "$MASTER_PID_FILE" ]; then
        local m_pid
        m_pid=$(cat "$MASTER_PID_FILE" 2>/dev/null || true)
        if [ -n "$m_pid" ] && [ "$m_pid" != "$$" ] && kill -0 "$m_pid" 2>/dev/null; then
            kill -TERM "$m_pid" 2>/dev/null || true
            sleep 0.5
        fi
        rm -f "$MASTER_PID_FILE"
    fi

    rm -f "$STOP_FLAG_FILE"
    # Clean up empty runtime directory
    rmdir "$RUNTIME_DIR" 2>/dev/null || true

    if [ "$stopped_any" -eq 1 ]; then
        echo -e "${GREEN}${BOLD}MassCommAI application processes stopped successfully.${NC}"
    else
        echo -e "${YELLOW}No active MassCommAI application processes were running.${NC}"
    fi

    echo -e "${CYAN}Note: PostgreSQL database and Redis services remain intact.${NC}"
    echo -e "${BOLD}${BLUE}==================================================${NC}"
}

# Find suitable Python environment that has required dependencies installed
detect_python_env() {
    PYTHON_BIN=""

    # Candidate evaluation order:
    # 1. Currently active virtualenv ($VIRTUAL_ENV)
    # 2. backend/.venv
    # 3. .venv at repository root
    # 4. User's pyenv python 3.13.14 (known verified environment)
    # 5. System python3
    local candidates=(
        "${VIRTUAL_ENV:-}/bin/python"
        "$BACKEND_DIR/.venv/bin/python"
        "$REPO_ROOT/.venv/bin/python"
        "$HOME/.pyenv/versions/3.13.14/bin/python"
        "$(command -v python3 2>/dev/null || true)"
    )

    for cand in "${candidates[@]}"; do
        if [ -n "$cand" ] && [ -x "$cand" ]; then
            if "$cand" -c "import fastapi, uvicorn, sqlalchemy, alembic, psycopg, pydantic_settings, apscheduler" >/dev/null 2>&1; then
                PYTHON_BIN="$cand"
                return 0
            fi
        fi
    done

    # If no candidate satisfied all dependencies, check if at least a virtual environment exists
    for cand in "${candidates[@]}"; do
        if [ -n "$cand" ] && [ -x "$cand" ]; then
            PYTHON_BIN="$cand"
            return 1
        fi
    done

    return 2
}

# Test live PostgreSQL database connectivity
check_postgres_connected() {
    [ -n "$PYTHON_BIN" ] || return 1
    (cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -c "
import sys
from app.core.config import settings
from sqlalchemy import create_engine, text
try:
    engine = create_engine(settings.DATABASE_URL, connect_args={'connect_timeout': 3})
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    sys.exit(0)
except Exception:
    sys.exit(1)
" >/dev/null 2>&1)
}

# Test live Redis connectivity
check_redis_connected() {
    [ -n "$PYTHON_BIN" ] || return 1
    (cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -c "
import sys
from app.core.config import settings
import redis
url = settings.REDIS_URL or 'redis://127.0.0.1:6379/0'
try:
    client = redis.from_url(url, socket_connect_timeout=1.0)
    client.ping()
    sys.exit(0)
except Exception:
    sys.exit(1)
" >/dev/null 2>&1)
}

# Start or reuse PostgreSQL and Redis via Docker Compose
start_docker_services() {
    echo -e "${BOLD}Checking Docker environment...${NC}"
    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Docker command not found.${NC}"
        echo "Please install Docker Desktop or run without --docker using local PostgreSQL."
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Docker daemon is not running.${NC}"
        echo "Please start Docker Desktop and ensure the daemon is accessible, then try again."
        exit 1
    fi

    local compose_services=""
    if check_postgres_connected; then
        echo -e "  PostgreSQL     : ${GREEN}Already running locally${NC} (Reusing localhost:5432)"
    else
        compose_services="$compose_services db"
    fi

    if check_redis_connected; then
        echo -e "  Redis          : ${GREEN}Already running locally${NC} (Reusing 127.0.0.1:6379)"
    else
        compose_services="$compose_services redis"
    fi

    if [ -n "$compose_services" ]; then
        echo -e "${CYAN}Starting container(s) via Docker Compose:${compose_services}...${NC}"
        (cd "$REPO_ROOT" && docker compose up -d $compose_services)
    fi

    echo -n "Waiting for database and Redis services to become ready..."
    local ready=0
    for i in $(seq 1 40); do
        if check_postgres_connected && check_redis_connected; then
            ready=1
            break
        fi
        echo -n "."
        sleep 1
    done

    if [ "$ready" -eq 1 ]; then
        echo -e " ${GREEN}Ready!${NC}"
    else
        echo -e " ${RED}Failed!${NC}"
        echo -e "${RED}[ERROR] Database or Redis service did not become healthy within 40 seconds.${NC}"
        echo "Check container status: docker compose ps"
        exit 1
    fi
}

# Main Application Startup Workflow
start_application() {
    local use_docker="$1"
    print_banner

    # 1. Environment & Dependency Validation
    echo -e "${BOLD}[1/5] Checking environment and dependencies...${NC}"

    # Check environment files
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        if [ -f "$BACKEND_DIR/.env.example" ]; then
            echo -e "${YELLOW}[WARNING] backend/.env not found. Initializing from backend/.env.example...${NC}"
            cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
        else
            echo -e "${RED}[ERROR] Missing backend/.env file.${NC}"
            exit 1
        fi
    fi

    if [ ! -f "$FRONTEND_DIR/.env" ]; then
        if [ -f "$FRONTEND_DIR/.env.example" ]; then
            echo -e "${YELLOW}[WARNING] frontend/.env not found. Initializing from frontend/.env.example...${NC}"
            cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
        fi
    fi

    # Detect Python environment
    detect_python_env
    local py_status=$?

    if [ "$py_status" -eq 2 ]; then
        echo -e "${RED}[ERROR] No Python 3 environment found.${NC}"
        echo "Please install Python 3.13+ or configure a virtual environment in backend/.venv"
        exit 1
    elif [ "$py_status" -eq 1 ]; then
        echo -e "${RED}[ERROR] Python environment at $PYTHON_BIN is missing required dependencies.${NC}"
        echo -e "To install backend dependencies, run:"
        echo -e "    ${BOLD}$PYTHON_BIN -m pip install -r backend/requirements.txt${NC}"
        exit 1
    fi
    echo -e "  Python runtime : ${GREEN}$PYTHON_BIN${NC} ($("$PYTHON_BIN" --version 2>&1))"

    # Check Node.js and npm
    if ! command -v node >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Node.js is not installed or not in PATH.${NC}"
        echo "Please install Node.js (v20+ recommended) and try again."
        exit 1
    fi
    if ! command -v npm >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] npm is not installed or not in PATH.${NC}"
        exit 1
    fi
    echo -e "  Node / npm     : ${GREEN}$(node --version)${NC} / ${GREEN}$(npm --version)${NC}"

    # Check Frontend node_modules
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo -e "${RED}[ERROR] Frontend dependencies are missing (frontend/node_modules not found).${NC}"
        echo -e "To install frontend dependencies, run:"
        echo -e "    ${BOLD}cd frontend && npm install${NC}"
        exit 1
    fi

    # Check curl
    if ! command -v curl >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] curl command is required for health-check probes.${NC}"
        exit 1
    fi

    # Check for duplicate running processes
    if [ -f "$BACKEND_PID_FILE" ]; then
        local existing_b_pid
        existing_b_pid=$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)
        if is_pid_valid "$existing_b_pid" "uvicorn|python"; then
            echo -e "${YELLOW}[WARNING] MassCommAI Backend is already running (PID: $existing_b_pid).${NC}"
            echo -e "Run ${BOLD}./start.sh --status${NC} to inspect or ${BOLD}./start.sh --stop${NC} to stop it."
            exit 1
        else
            rm -f "$BACKEND_PID_FILE"
        fi
    fi

    if [ -f "$FRONTEND_PID_FILE" ]; then
        local existing_f_pid
        existing_f_pid=$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)
        if is_pid_valid "$existing_f_pid" "vite|npm|node"; then
            echo -e "${YELLOW}[WARNING] MassCommAI Frontend is already running (PID: $existing_f_pid).${NC}"
            echo -e "Run ${BOLD}./start.sh --status${NC} to inspect or ${BOLD}./start.sh --stop${NC} to stop it."
            exit 1
        else
            rm -f "$FRONTEND_PID_FILE"
        fi
    fi

    # 2. Database and Redis Readiness
    echo -e "${BOLD}[2/5] Checking database and caching services...${NC}"

    if [ "$use_docker" = "true" ]; then
        start_docker_services
    else
        # Local services mode
        if check_postgres_connected; then
            echo -e "  PostgreSQL     : ${GREEN}Connected${NC} (Accepting connections)"
        else
            echo -e "${RED}[ERROR] PostgreSQL database is unreachable at the configured DATABASE_URL.${NC}"
            echo ""
            echo "To start PostgreSQL locally (if installed via Homebrew):"
            echo -e "    ${BOLD}brew services start postgresql@16${NC}"
            echo ""
            echo "Or launch database services via Docker Compose:"
            echo -e "    ${BOLD}./start.sh --docker${NC}"
            exit 1
        fi

        if check_redis_connected; then
            echo -e "  Redis          : ${GREEN}Connected${NC} (127.0.0.1:6379)"
            REDIS_STATUS="Connected (127.0.0.1:6379)"
        else
            echo -e "  Redis          : ${YELLOW}In-Memory Mode${NC} (Local rate limiter active)"
            REDIS_STATUS="In-Memory Mode (Active)"
        fi
    fi

    # 3. Database Migrations
    echo -e "${BOLD}[3/5] Checking database schema and running migrations...${NC}"
    local migration_output=""
    if ! migration_output=$(cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -m alembic upgrade head 2>&1); then
        echo -e "${RED}[ERROR] Alembic database migration failed:${NC}"
        echo "$migration_output"
        exit 1
    fi
    local alembic_rev=""
    alembic_rev=$(cd "$BACKEND_DIR" && PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -m alembic current 2>/dev/null | grep -E "^[a-f0-9]+" | head -n 1 || echo "Up to date")
    echo -e "  Alembic schema : ${GREEN}Up to date${NC} (Head: ${BOLD}$alembic_rev${NC})"

    # Prepare directories
    mkdir -p "$RUNTIME_DIR" "$LOGS_DIR"
    echo "$$" > "$MASTER_PID_FILE"
    rm -f "$STOP_FLAG_FILE"

    # 4. Start Backend
    echo -e "${BOLD}[4/5] Starting FastAPI backend on http://$BACKEND_HOST:$BACKEND_PORT...${NC}"

    # Verify backend port is free
    if nc -z "$BACKEND_HOST" "$BACKEND_PORT" 2>/dev/null; then
        echo -e "${RED}[ERROR] Port $BACKEND_PORT is already in use by another process.${NC}"
        echo "Please stop the process using port $BACKEND_PORT before running start.sh."
        exit 1
    fi

    # Launch uvicorn in background
    (cd "$BACKEND_DIR" && exec env PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload) >> "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

    printf "  Waiting for backend health check"
    local b_ready=0
    for i in $(seq 1 40); do
        if curl -s -f "http://$BACKEND_HOST:$BACKEND_PORT/health" >/dev/null 2>&1; then
            b_ready=1
            break
        fi
        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo -e " ${RED}Failed!${NC}"
            echo -e "${RED}[ERROR] Backend process terminated unexpectedly during startup.${NC}"
            echo "Inspect backend logs at: $BACKEND_LOG"
            rm -f "$BACKEND_PID_FILE"
            exit 1
        fi
        printf "."
        sleep 0.5
    done

    if [ "$b_ready" -eq 1 ]; then
        echo -e " ${GREEN}Ready (PID: $BACKEND_PID)${NC}"
    else
        echo -e " ${RED}Timed out!${NC}"
        echo -e "${RED}[ERROR] Backend did not respond on http://$BACKEND_HOST:$BACKEND_PORT/health within 20 seconds.${NC}"
        echo "Inspect backend logs at: $BACKEND_LOG"
        stop_process "$BACKEND_PID" "Backend"
        rm -f "$BACKEND_PID_FILE"
        exit 1
    fi

    # 5. Start Frontend
    echo -e "${BOLD}[5/5] Starting Vite frontend server on http://$FRONTEND_HOST:$FRONTEND_PORT...${NC}"

    # Verify frontend port is free
    if nc -z "$FRONTEND_HOST" "$FRONTEND_PORT" 2>/dev/null; then
        echo -e "${RED}[ERROR] Port $FRONTEND_PORT is already in use by another process.${NC}"
        echo "Please stop the process using port $FRONTEND_PORT before running start.sh."
        stop_process "$BACKEND_PID" "Backend"
        rm -f "$BACKEND_PID_FILE"
        exit 1
    fi

    # Launch npm run dev in background
    (cd "$FRONTEND_DIR" && exec npm run dev) >> "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

    printf "  Waiting for frontend server"
    local f_ready=0
    for i in $(seq 1 40); do
        if curl -s -f "http://$FRONTEND_HOST:$FRONTEND_PORT" >/dev/null 2>&1; then
            f_ready=1
            break
        fi
        if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            echo -e " ${RED}Failed!${NC}"
            echo -e "${RED}[ERROR] Frontend process terminated unexpectedly during startup.${NC}"
            echo "Inspect frontend logs at: $FRONTEND_LOG"
            stop_process "$BACKEND_PID" "Backend"
            rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
            exit 1
        fi
        printf "."
        sleep 0.5
    done

    if [ "$f_ready" -eq 1 ]; then
        echo -e " ${GREEN}Ready (PID: $FRONTEND_PID)${NC}"
    else
        echo -e " ${YELLOW}Slow startup (PID: $FRONTEND_PID)${NC}"
        echo -e "${YELLOW}[NOTE] Frontend is taking longer to initialize. It may still be compiling assets.${NC}"
    fi

    # Display Startup Summary
    echo ""
    echo -e "${BOLD}${BLUE}==================================================${NC}"
    echo -e "${BOLD}${GREEN}             MASSCOMMAI STARTED                   ${NC}"
    echo -e "${BOLD}${BLUE}==================================================${NC}"
    echo ""
    echo -e "  Frontend       : ${BOLD}${CYAN}http://localhost:$FRONTEND_PORT${NC}"
    echo -e "  Backend API    : ${BOLD}${CYAN}http://localhost:$BACKEND_PORT${NC}"
    echo -e "  Swagger Docs   : ${BOLD}http://localhost:$BACKEND_PORT/docs${NC}"
    echo -e "  Health Check   : ${BOLD}http://localhost:$BACKEND_PORT/health${NC}"
    echo ""
    echo -e "  PostgreSQL     : ${GREEN}Connected${NC}"
    echo -e "  Redis          : ${GREEN}${REDIS_STATUS:-Connected}${NC}"
    echo -e "  Alembic        : ${GREEN}Up to date${NC} (${BOLD}$alembic_rev${NC})"
    echo ""
    echo -e "  Logs:"
    echo -e "    Backend      : ${CYAN}logs/backend.log${NC}"
    echo -e "    Frontend     : ${CYAN}logs/frontend.log${NC}"
    echo ""
    echo -e "${BOLD}Press Ctrl+C to stop the application.${NC}"
    echo -e "${BOLD}${BLUE}==================================================${NC}"

    # Graceful shutdown handler for Ctrl+C
    cleanup_and_exit() {
        echo ""
        rm -f "$MASTER_PID_FILE" "$STOP_FLAG_FILE"
        stop_application
        exit 0
    }
    trap cleanup_and_exit SIGINT SIGTERM

    # Foreground process monitor loop
    while true; do
        if [ -f "$STOP_FLAG_FILE" ]; then
            rm -f "$STOP_FLAG_FILE" "$MASTER_PID_FILE"
            exit 0
        fi

        if ! is_pid_valid "$BACKEND_PID" "uvicorn|python"; then
            if [ -f "$STOP_FLAG_FILE" ] || [ ! -f "$BACKEND_PID_FILE" ]; then
                rm -f "$STOP_FLAG_FILE" "$MASTER_PID_FILE"
                exit 0
            fi
            echo ""
            echo -e "${RED}[ERROR] Backend process (PID $BACKEND_PID) stopped unexpectedly.${NC}"
            echo "Check backend log: $BACKEND_LOG"
            stop_application
            exit 1
        fi
        if ! is_pid_valid "$FRONTEND_PID" "vite|npm|node"; then
            if [ -f "$STOP_FLAG_FILE" ] || [ ! -f "$FRONTEND_PID_FILE" ]; then
                rm -f "$STOP_FLAG_FILE" "$MASTER_PID_FILE"
                exit 0
            fi
            echo ""
            echo -e "${RED}[ERROR] Frontend process (PID $FRONTEND_PID) stopped unexpectedly.${NC}"
            echo "Check frontend log: $FRONTEND_LOG"
            stop_application
            exit 1
        fi
        sleep 2
    done
}

# Command dispatching
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --status)
        check_status
        exit 0
        ;;
    --stop)
        stop_application
        exit 0
        ;;
    --docker)
        start_application "true"
        ;;
    "")
        start_application "false"
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        echo "Run ./start.sh --help for available options."
        exit 1
        ;;
esac
