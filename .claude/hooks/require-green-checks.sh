#!/usr/bin/env bash
# PreToolUse hook for the python-developer agent in CI. The developer workflow
# wires it up through the action's `settings` input, not through
# `.claude/settings.json`, so local sessions are unaffected.
#
# It refuses a push or `gh pr create` until the checks CI runs pass, and hands
# the failure back to the agent (exit 2 + stderr) so it can fix it. The role
# file already asks for these checks; this makes them impossible to skip. The
# README quickstart (#97) shipped three red pushes when they were only asked
# for. See AGENTS.md §15.
#
# On PR runs the action restores `.claude/` from the base branch before Claude
# starts, so a pull request cannot weaken this script for its own run.
set -uo pipefail

command=$(jq -r '.tool_input.command // empty')
case "$command" in
  # Tag mode pushes through the action's `git-push.sh` wrapper.
  *git-push.sh* | *"git push"* | *"gh pr create"*) ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 2

# The checks see the working tree, the push sends commits; refuse until they agree.
if ! git diff --quiet HEAD --; then
  echo "Refused: tracked files have uncommitted changes, so the checks would not test what gets pushed. Commit or discard them, then push (or open the PR) as a command of its own." >&2
  exit 2
fi

# A push followed by `gh pr create` on the same commit runs the checks once.
head=$(git rev-parse HEAD)
passed="${RUNNER_TEMP:-/tmp}/green-checks-$head"
[ -f "$passed" ] && exit 0

log=$(mktemp)
check() {
  if ! "$@" >"$log" 2>&1; then
    {
      echo "Refused: \`$*\` failed. Fix what it reports (never suppress it), commit, and try again. Last lines:"
      tail -n 60 "$log"
    } >&2
    exit 2
  fi
}

check uv run ruff check
check uv run ruff format --check
check uv run ty check
check uv run pytest -q

touch "$passed"
exit 0
