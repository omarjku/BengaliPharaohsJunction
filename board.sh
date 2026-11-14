#!/bin/bash
# Agent message board: one pinned GitHub issue that every teammate's AI agent reads and posts to.
# Run inside the team repo's folder. Needs the GitHub CLI (gh) logged in.
#   ./board.sh init           create + pin the "Message Board" issue (once per team)
#   ./board.sh read [N]       show the last N posts (default 15)
#   ./board.sh post "text"    post as "[$AGENT_NAME] text"  (set AGENT_NAME, e.g. "Zoha's agent")
set -euo pipefail
num() { gh api 'repos/{owner}/{repo}/issues?labels=message-board&state=open' -q '.[0].number'; }  # REST: no search-index lag
case "${1:-read}" in
  init)
    gh label create message-board --color 5319E7 --description "Agent coordination board" 2>/dev/null || true
    n=$(gh issue create --title "Message Board" --label message-board \
        --body "Agents and humans post status, claims, handoffs and review requests here. Newest at the bottom." | grep -o '[0-9]*$')
    gh issue pin "$n"; echo "Message Board is issue #$n" ;;
  read)
    gh issue view "$(num)" --json comments \
      -q "[.comments[] | select(.authorAssociation==\"OWNER\" or .authorAssociation==\"MEMBER\" or .authorAssociation==\"COLLABORATOR\")][-${2:-15}:][] | \"\(.createdAt[5:16]) \(.author.login): \(.body)\"" ;;  # team posts only: the repo is public
  post)
    [ -n "${AGENT_NAME:-}" ] || { echo 'set AGENT_NAME first, e.g. export AGENT_NAME="Omar agent"' >&2; exit 2; }
    gh issue comment "$(num)" --body "[$AGENT_NAME] ${2:?message text}" >/dev/null && echo posted ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
