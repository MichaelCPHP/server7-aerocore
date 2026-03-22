#!/bin/bash
# AeroCore Lab Platform — Double-click to open
cd "$(dirname "$0")"
export SERVER_ROOT="$(cd .. && pwd)"
export GENESIS_DIR="${SERVER_ROOT}/genesis"
node launcher.js
