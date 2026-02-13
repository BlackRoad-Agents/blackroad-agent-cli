#!/bin/bash

: "${BR_MAX_READ_LINES:=200}"

br_command_has_shell_ops() {
  case "$1" in
    *'>'*|*'<'*|*'|'*|*'&'*|*';'*)
      return 0
      ;;
  esac
  return 1
}

br_is_read_only_command() {
  local command="$1"
  local first=""
  local -a parts=()

  br_command_has_shell_ops "$command" && return 1

  IFS=' ' read -r -a parts <<< "$command"
  first="${parts[0]:-}"
  if [ -z "$first" ]; then
    return 1
  fi

  case "$first" in
    ls|pwd|whoami|date|uname|df|du|ps|uptime|id|cat|head|tail|grep|rg|stat|wc|tree|ollama)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

br_confirm_action() {
  local prompt="$1"
  local reply=""

  if [ ! -t 0 ]; then
    printf '%s\n' "Confirmation required but no TTY available." >&2
    return 1
  fi

  printf '%s' "$prompt [y/N] " >&2
  read -r reply < /dev/tty
  case "$reply" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

br_print_action_block() {
  local header="$1"
  shift
  printf '%s\n' "$header"
  while [ $# -gt 0 ]; do
    printf '%s\n' "$1"
    shift
  done
}

br_action_read_file() {
  local path="$1"
  local dry_run="$2"

  if [ -z "$path" ]; then
    printf '%s\n' "Missing path for read_file action." >&2
    return
  fi

  if [ "$dry_run" -eq 1 ]; then
    br_print_action_block "[ACTION_DRY_RUN]" "type=read_file" "path=$path"
    return
  fi

  if [ ! -f "$path" ]; then
    printf '%s\n' "File not found: $path" >&2
    return
  fi

  br_print_action_block "[ACTION_RESULT]" "type=read_file" "path=$path" "note=truncated_to_${BR_MAX_READ_LINES}_lines" "---"
  sed -n "1,${BR_MAX_READ_LINES}p" "$path"
  printf '%s\n' "---"
}

br_action_run_command() {
  local command="$1"
  local dry_run="$2"
  local status=0
  local -a parts=()

  if [ -z "$command" ]; then
    printf '%s\n' "Missing command for run_command action." >&2
    return
  fi

  if [ "$dry_run" -eq 1 ]; then
    br_print_action_block "[ACTION_DRY_RUN]" "type=run_command" "command=$command"
    return
  fi

  IFS=' ' read -r -a parts <<< "$command"
  if [ "${#parts[@]}" -eq 0 ]; then
    printf '%s\n' "Empty command for run_command action." >&2
    return
  fi

  if ! br_is_read_only_command "$command"; then
    if ! br_confirm_action "Run command: $command"; then
      printf '%s\n' "Skipped command: $command" >&2
      return
    fi
  fi

  br_print_action_block "[ACTION_RESULT]" "type=run_command" "command=$command" "---"
  set +e
  "${parts[@]}"
  status=$?
  set -e
  printf '%s\n' "status=$status"
  printf '%s\n' "---"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "Command failed with exit code $status." >&2
  fi
}

br_run_action() {
  local action_type="$1"
  local action_path="$2"
  local action_command="$3"
  local dry_run="$4"

  if [ -z "$action_type" ]; then
    return
  fi

  case "$action_type" in
    read_file)
      br_action_read_file "$action_path" "$dry_run"
      ;;
    run_command)
      br_action_run_command "$action_command" "$dry_run"
      ;;
    *)
      printf '%s\n' "Unknown action type: $action_type" >&2
      ;;
  esac
}

br_handle_actions() {
  local output="$1"
  local dry_run="$2"
  local line=""
  local in_action=0
  local action_type=""
  local action_path=""
  local action_command=""

  while IFS= read -r line; do
    if [ "$line" = "[ACTION]" ]; then
      if [ "$in_action" -eq 1 ]; then
        br_run_action "$action_type" "$action_path" "$action_command" "$dry_run"
      fi
      in_action=1
      action_type=""
      action_path=""
      action_command=""
      continue
    fi

    if [ "$in_action" -eq 1 ]; then
      if [ -n "$line" ] && [[ "$line" == *=* ]]; then
        local key="${line%%=*}"
        local value="${line#*=}"
        case "$key" in
          type)
            action_type="$value"
            ;;
          path)
            action_path="$value"
            ;;
          command)
            action_command="$value"
            ;;
        esac
      else
        br_run_action "$action_type" "$action_path" "$action_command" "$dry_run"
        in_action=0
      fi
    fi
  done <<EOF
$output
EOF

  if [ "$in_action" -eq 1 ]; then
    br_run_action "$action_type" "$action_path" "$action_command" "$dry_run"
  fi
}
