#!/bin/bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
case "$SCRIPT_PATH" in
  */*)
    ROOT_DIR="${SCRIPT_PATH%/*}"
    ;;
  *)
    ROOT_DIR="."
    ;;
esac

BIN_DIR="/usr/local/bin"
SHARE_DIR="/usr/local/share/blackroad-agent-cli"

mkdir -p "$BIN_DIR"
mkdir -p "$SHARE_DIR"

ln -sfn "$ROOT_DIR/lib" "$SHARE_DIR/lib"

ln -sfn "$ROOT_DIR/agents/planner.sh" "$BIN_DIR/br-agent-planner"
ln -sfn "$ROOT_DIR/agents/analyst.sh" "$BIN_DIR/br-agent-analyst"
ln -sfn "$ROOT_DIR/agents/docwriter.sh" "$BIN_DIR/br-agent-docwriter"
ln -sfn "$ROOT_DIR/agents/operator.sh" "$BIN_DIR/br-agent-operator"
ln -sfn "$ROOT_DIR/agents/auditor.sh" "$BIN_DIR/br-agent-auditor"

printf '%s\n' "Installed agent CLIs to $BIN_DIR:"
printf '%s\n' "  br-agent-planner"
printf '%s\n' "  br-agent-analyst"
printf '%s\n' "  br-agent-docwriter"
printf '%s\n' "  br-agent-operator"
printf '%s\n' "  br-agent-auditor"
printf '%s\n' ""
printf '%s\n' "Shared libs symlinked to $SHARE_DIR/lib"
printf '%s\n' "If installation failed due to permissions, re-run with sudo."
