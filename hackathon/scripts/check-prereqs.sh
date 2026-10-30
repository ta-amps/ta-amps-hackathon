#!/usr/bin/env bash
# Report whether the tools the project needs are installed. Installs nothing.
# Usage: scripts/check-prereqs.sh
set -uo pipefail

status=0
row() { printf '%-10s %-24s %-22s %s\n' "$1" "$2" "$3" "$4"; }

version_ge() {  # version_ge FOUND WANT -> true if FOUND >= WANT
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

check() {  # check NAME NEED_VERSION COMMAND [required|optional]
  local name="$1" need="$2" cmd="$3" kind="${4:-required}" found=""
  if command -v "${cmd%% *}" >/dev/null 2>&1; then
    found="$($cmd 2>&1 | head -n1 | grep -Eo '[0-9]+(\.[0-9]+)+' | head -n1)"
    if [ -z "$need" ] || { [ -n "$found" ] && version_ge "$found" "$need"; }; then
      row "$name" "${need:+>= $need}" "${found:-present}" "ok"
      return
    fi
    row "$name" ">= $need" "${found:-unknown}" "TOO OLD"
  else
    row "$name" "${need:+>= $need}" "missing" "$([ "$kind" = optional ] && echo "optional" || echo "MISSING")"
  fi
  [ "$kind" = optional ] || status=1
}

row "tool" "needed" "found" "status"
row "----" "------" "-----" "------"
if command -v uv >/dev/null 2>&1; then
  check "uv" "" "uv --version"
  row "python" ">= 3.12 (uv provides)" "via uv" "ok"
else
  check "python3" "3.12" "python3 --version"
fi
check "node" "22.13" "node --version"
check "pnpm" "" "pnpm --version"
check "git" "" "git --version"
check "gh" "" "gh --version" optional
check "make" "" "make --version"
check "jq" "" "jq --version" optional
if [ "$(uname -s)" = "Linux" ]; then
  check "bwrap" "" "bwrap --version"   # Muse Code's Linux sandbox needs a working bubblewrap
fi

echo
if [ "$status" -eq 0 ]; then
  echo "All required tools are present."
else
  echo "Something required is missing or too old; see the table above. Nothing was installed."
fi
exit "$status"
