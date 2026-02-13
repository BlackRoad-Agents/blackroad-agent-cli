#!/bin/bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
case "$SCRIPT_PATH" in
  */*)
    SCRIPT_DIR="${SCRIPT_PATH%/*}"
    ;;
  *)
    SCRIPT_DIR="."
    ;;
esac

LIB_DIR=""
if [ -n "${BR_AGENT_HOME:-}" ]; then
  LIB_DIR="$BR_AGENT_HOME/lib"
elif [ -f "$SCRIPT_DIR/../lib/common.sh" ]; then
  LIB_DIR="$SCRIPT_DIR/../lib"
elif [ -f "/usr/local/share/blackroad-agent-cli/lib/common.sh" ]; then
  LIB_DIR="/usr/local/share/blackroad-agent-cli/lib"
elif [ -f "/usr/local/lib/blackroad-agent-cli/lib/common.sh" ]; then
  LIB_DIR="/usr/local/lib/blackroad-agent-cli/lib"
else
  printf '%s\n' "Error: Unable to locate lib directory. Set BR_AGENT_HOME." >&2
  exit 1
fi

. "$LIB_DIR/common.sh"
. "$LIB_DIR/prompts.sh"
. "$LIB_DIR/actions.sh"

AGENT_NAME="auditor"
AGENT_DESC="Compliance-focused review and requirement validation."
DEFAULT_MODEL="blackroad-auditor"
SYSTEM_PROMPT="$(br_prompt_auditor)"

br_agent_cli "$AGENT_NAME" "$DEFAULT_MODEL" "$SYSTEM_PROMPT" "$AGENT_DESC" "$@"
