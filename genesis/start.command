#!/bin/bash
# Genesis IDE — Double-click to launch
cd "$(dirname "$0")"

# Derive server root and read port from server.json
SERVER_ROOT="$(cd .. && pwd)"
PORT_BASE=$(python3 -c "import json; print(json.load(open('${SERVER_ROOT}/server.json')).get('portBase', 9000))" 2>/dev/null || echo 9000)
GENESIS_PORT=$((PORT_BASE + 199))

# Kill any orphaned processes on known ports before starting
echo "Checking for orphaned processes..."
KILLED=0

# Kill Genesis port
for PID in $(lsof -ti:${GENESIS_PORT} 2>/dev/null); do
  kill -9 "$PID" 2>/dev/null && KILLED=$((KILLED + 1))
done

# Kill platform instance ports (read from platforms.json)
if [ -f platforms.json ]; then
  PORTS=$(python3 -c "
import json, os
platforms = json.load(open('platforms.json'))
for p in platforms:
    ppath = p['path'] if os.path.isabs(p['path']) else os.path.join('${SERVER_ROOT}', p['path'])
    idir = os.path.join(ppath, 'instances')
    if not os.path.isdir(idir): continue
    for name in os.listdir(idir):
        lj = os.path.join(idir, name, 'lab.json')
        if not os.path.isfile(lj): continue
        cfg = json.load(open(lj))
        port = cfg.get('port')
        if port:
            print(port)
            print(port + 70)
" 2>/dev/null)
  for PORT in $PORTS; do
    for PID in $(lsof -ti:${PORT} 2>/dev/null); do
      kill -9 "$PID" 2>/dev/null && KILLED=$((KILLED + 1))
    done
  done
fi

if [ $KILLED -gt 0 ]; then
  echo "Killed $KILLED orphaned process(es)"
  sleep 1
fi

echo "Starting Genesis IDE on port ${GENESIS_PORT}..."
echo "Server root: ${SERVER_ROOT}"

SERVER_ROOT="${SERVER_ROOT}" \
LAB_IS_GENESIS=1 \
LAB_INSTANCE="$(pwd)" \
LAB_PORT="${GENESIS_PORT}" \
GENESIS_DIR="$(pwd)" \
GLOBAL_PLUGINS_DIR="$(pwd)/template/plugins" \
GLOBAL_SKILLS_DIR="$(pwd)/template/skills" \
node template/core/server.js
