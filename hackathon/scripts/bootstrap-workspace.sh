#!/usr/bin/env bash
# Clone this kit and your own repos side by side into one workspace folder.
# The kit is the hackathon/ folder of the ta-amps/teleionlabs-teleion-fabric repo, so it lands in teleionlabs-teleion-fabric/hackathon/.
# Usage: scripts/bootstrap-workspace.sh WORKSPACE_DIR [REPO ...]
#   REPO is owner/name (cloned from GitHub) or any git URL.
# Example: scripts/bootstrap-workspace.sh ~/hackathon you/your-app you/your-backend
# Uses `gh repo clone` for owner/name when gh is installed and signed in, otherwise git over HTTPS.
set -euo pipefail

KIT="ta-amps/teleionlabs-teleion-fabric"
WORKSPACE="${1:?usage: scripts/bootstrap-workspace.sh WORKSPACE_DIR [REPO ...]}"
shift

mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

clone() {
  local spec="$1" dir
  dir="$(basename "${spec%.git}")"
  if [ -d "$dir/.git" ]; then
    echo "skip   $dir (already cloned)"
    return
  fi
  case "$spec" in
    *://*|git@*) git clone "$spec" "$dir" ;;
    */*)
      if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        gh repo clone "$spec" "$dir"
      else
        git clone "https://github.com/$spec.git" "$dir"
      fi ;;
    *) echo "not a repo: $spec (use owner/name or a git URL)" >&2; return 1 ;;
  esac
  echo "cloned $dir"
}

clone "$KIT"
for repo in "$@"; do clone "$repo"; done

cat <<EOT

Workspace ready in $(pwd). Next:
  1. teleionlabs-teleion-fabric/hackathon/scripts/check-prereqs.sh
  2. In each of your repos, install the agent templates: teleionlabs-teleion-fabric/hackathon/agents/README.md
  3. Plan with teleionlabs-teleion-fabric/hackathon/guides/ten-day-plan.md; check rules with guides/compliance-checklist.md
  4. Keep keys in each repo's .env (gitignored); never paste them into a chat.
EOT
