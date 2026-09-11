#!/bin/sh
# Container entrypoint for the MCP server (Dockerfile.mcp): seed the job pool
# into the container's own (ephemeral) database, then serve over streamable
# HTTP on the port Cloud Run hands us.
set -e
export RECRUITER_MCP_PORT="${PORT:-8080}"
mkdir -p "${OPEN_RECRUITER_DATA_DIR:-/tmp/open-recruiter}"
# The embeddings key is the same platform key charbit's server carries in its
# env-file secret; read it from there when it is mounted and nothing set it.
if [ -z "${EMBEDDING_API_KEY:-}" ] && [ -f /secrets/env ]; then
  export EMBEDDING_API_KEY="$(sed -n 's/^CHARBIT_AI_API_KEY=//p' /secrets/env | tr -d '"' | head -1)"
fi
python -m app.seed_jobs
exec python -m app.mcp_server
