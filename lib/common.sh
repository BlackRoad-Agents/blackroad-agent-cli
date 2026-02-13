#!/bin/bash

br_abort() {
  printf '%s\n' "Error: $*" >&2
  exit 1
}

br_print_usage() {
  local agent_name="$1"
  local default_model="$2"
  local description="$3"

  printf '%s\n' "Usage: br-agent-$agent_name [--model MODEL] [--dry-run] [--explain] [--help] [PROMPT]"
  printf '%s\n' ""
  printf '%s\n' "$description"
  printf '%s\n' ""
  printf '%s\n' "Options:"
  printf '%s\n' "  --model    Override the default Ollama model (default: $default_model)"
  printf '%s\n' "  --dry-run  Do not execute actions; print what would happen"
  printf '%s\n' "  --explain  Describe intended actions only; no action execution"
  printf '%s\n' "  --help     Show this help"
  printf '%s\n' ""
  printf '%s\n' "Input:"
  printf '%s\n' "  br-agent-$agent_name \"Do something\""
  printf '%s\n' "  cat file.txt | br-agent-$agent_name"
}

br_join_args() {
  local out=""
  local arg=""
  for arg in "$@"; do
    if [ -n "$out" ]; then
      out="$out $arg"
    else
      out="$arg"
    fi
  done
  printf '%s' "$out"
}

br_read_stdin() {
  local input=""
  local line=""
  while IFS= read -r line; do
    input="${input}${line}"$'\n'
  done
  printf '%s' "$input"
}

br_check_ollama() {
  command -v ollama >/dev/null 2>&1 || br_abort "ollama not found in PATH"
}

br_parse_args() {
  local default_model="$1"
  shift

  BR_MODEL="$default_model"
  BR_DRY_RUN=0
  BR_EXPLAIN=0
  BR_SHOW_HELP=0
  BR_PROMPT_ARGS=()

  while [ $# -gt 0 ]; do
    case "$1" in
      --help)
        BR_SHOW_HELP=1
        shift
        ;;
      --model)
        shift
        [ $# -gt 0 ] || br_abort "Missing value for --model"
        BR_MODEL="$1"
        shift
        ;;
      --dry-run)
        BR_DRY_RUN=1
        shift
        ;;
      --explain)
        BR_EXPLAIN=1
        shift
        ;;
      --)
        shift
        while [ $# -gt 0 ]; do
          BR_PROMPT_ARGS+=("$1")
          shift
        done
        ;;
      -*)
        br_abort "Unknown flag: $1"
        ;;
      *)
        BR_PROMPT_ARGS+=("$1")
        shift
        ;;
    esac
  done
}

br_resolve_prompt() {
  BR_PROMPT=""
  if [ "${#BR_PROMPT_ARGS[@]}" -gt 0 ]; then
    BR_PROMPT="$(br_join_args "${BR_PROMPT_ARGS[@]}")"
  else
    if [ -t 0 ]; then
      br_abort "No prompt provided"
    fi
    BR_PROMPT="$(br_read_stdin)"
  fi

  if [ -z "$BR_PROMPT" ]; then
    br_abort "Prompt is empty"
  fi
}

br_build_prompt() {
  local system_prompt="$1"
  local user_prompt="$2"
  local explain="$3"
  local explain_note=""

  if [ "$explain" -eq 1 ]; then
    explain_note="EXPLAIN MODE: Describe intended actions only. Do not output [ACTION] blocks."
  fi

  printf '%s\n' "SYSTEM PROMPT:"
  printf '%s\n' "$system_prompt"
  printf '%s\n' ""
  printf '%s\n' "USER PROMPT:"
  printf '%s\n' "$user_prompt"

  if [ -n "$explain_note" ]; then
    printf '%s\n' ""
    printf '%s\n' "$explain_note"
  fi
}

br_run_ollama() {
  local model="$1"
  local prompt="$2"
  printf '%s\n' "$prompt" | ollama run "$model"
}

br_agent_cli() {
  local agent_name="$1"
  local default_model="$2"
  local system_prompt="$3"
  local description="$4"
  shift 4

  br_parse_args "$default_model" "$@"
  if [ "$BR_SHOW_HELP" -eq 1 ]; then
    br_print_usage "$agent_name" "$default_model" "$description"
    exit 0
  fi

  br_resolve_prompt
  br_check_ollama

  local full_prompt=""
  full_prompt="$(br_build_prompt "$system_prompt" "$BR_PROMPT" "$BR_EXPLAIN")"

  local output=""
  output="$(br_run_ollama "$BR_MODEL" "$full_prompt")"
  printf '%s\n' "$output"

  if [ "$BR_EXPLAIN" -eq 0 ]; then
    br_handle_actions "$output" "$BR_DRY_RUN"
  fi
}
