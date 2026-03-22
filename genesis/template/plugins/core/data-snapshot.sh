#!/bin/bash
# Data Snapshot — commit data/output changes with a descriptive tag
# Usage: ./scripts/data-snapshot.sh "description of what changed"
#
# Example: ./scripts/data-snapshot.sh "re-encoded 12 ambiguous events"
# Creates: git commit + git tag data-YYYYMMDD-HHMMSS

set -e
cd "$(dirname "$0")/.."

MSG="${1:-data snapshot}"

# Check for changes
if git diff --quiet -- data/ output/ 2>/dev/null; then
  echo "No data changes to snapshot."
  exit 0
fi

# Stage and commit
git add data/ output/
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
git commit -m "data: ${MSG}"
git tag -a "data-${TIMESTAMP}" -m "${MSG}"

echo "Snapshot created: data-${TIMESTAMP}"
echo "  Message: ${MSG}"
echo "  Rollback: git checkout data-${TIMESTAMP} -- data/ output/"
