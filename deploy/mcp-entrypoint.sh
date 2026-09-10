#!/bin/sh
# Container entrypoint for the MCP server (Dockerfile.mcp): seed the job pool
# into the container's own (ephemeral) database, then serve over streamable
# HTTP on the port Cloud Run hands us.
set -e
export RECRUITER_MCP_PORT="${PORT:-8080}"
mkdir -p "${OPEN_RECRUITER_DATA_DIR:-/tmp/open-recruiter}"
python -m app.seed_jobs
exec python -m app.mcp_server
