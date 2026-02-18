#!/usr/bin/env bash
# ============================================================================
#  Open Recruiter — Start (Linux / macOS)
#  Run:  chmod +x start.sh && ./start.sh
# ============================================================================

ROOT="$(cd "$(dirname "$0")" && pwd)"
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "  ${CYAN}Starting Open Recruiter...${NC}"
echo ""

cleanup() {
    echo ""
    echo -e "  ${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo -e "  ${GREEN}Stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend
cd "$ROOT/backend"
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready (health check)
echo -e "  ${CYAN}Waiting for backend to start...${NC}"
RETRIES=0
MAX_RETRIES=60
while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:8000/docs >/dev/null 2>&1; then
        echo -e "  ${GREEN}Backend is ready.${NC}"
        break
    fi
    # Check if backend process died
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "  ${YELLOW}Backend process exited unexpectedly.${NC}"
        exit 1
    fi
    RETRIES=$((RETRIES + 1))
    sleep 1
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    echo -e "  ${YELLOW}Backend did not respond within ${MAX_RETRIES}s. Starting frontend anyway...${NC}"
fi

# Start frontend
cd "$ROOT/frontend"
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

sleep 2

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Open Recruiter is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  ${CYAN}Web UI:   http://localhost:5173${NC}"
echo -e "  ${CYAN}API:      http://localhost:8000${NC}"
echo -e "  ${CYAN}API Docs: http://localhost:8000/docs${NC}"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop.${NC}"
echo ""

# Keep alive, wait for either process
wait $BACKEND_PID $FRONTEND_PID
