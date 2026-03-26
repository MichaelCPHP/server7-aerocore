#!/bin/bash
# PreToolUse hook for Job Discipline enforcement
# Called by Claude CLI before each tool use
# Reads tool info from env vars, calls server endpoint, translates response

PORT="${LAB_PORT:-4210}"
TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
SESSION_ID="${CLAUDE_SESSION_ID:-}"

# Build JSON payload
PAYLOAD=$(python3 -c "
import json, os
print(json.dumps({
    'tool_name': os.environ.get('CLAUDE_TOOL_NAME', ''),
    'tool_input': json.loads(os.environ.get('CLAUDE_TOOL_INPUT', '{}')),
    'session_id': os.environ.get('CLAUDE_SESSION_ID', ''),
}))
" 2>/dev/null)

if [ -z "$PAYLOAD" ]; then
    exit 0  # Can't build payload, allow
fi

# Call the server hook endpoint
RESPONSE=$(curl -s -X POST "http://localhost:${PORT}/api/hooks/job-discipline" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD" 2>/dev/null)

if [ -z "$RESPONSE" ]; then
    exit 0  # No response, allow
fi

# Check if the response contains a deny decision
DECISION=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    hook = d.get('hookSpecificOutput', {})
    if hook.get('permissionDecision') == 'deny':
        reason = hook.get('permissionDecisionReason', 'Job discipline violation')
        print(json.dumps({'decision': 'block', 'reason': reason}))
    else:
        print('')
except:
    print('')
" 2>/dev/null)

if [ -n "$DECISION" ]; then
    echo "$DECISION"
fi
