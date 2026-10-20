#!/usr/bin/env bash
# Installs the learn research agent for Claude Code.
#   ~/.claude/agents/learn.md               subagent definition
#   ~/.claude/agents/hooks/safe-bash.py     safe_bash command blocker
#   ~/.local/bin/learn                      terminal command
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS="$HOME/.claude/agents"
BIN="${LEARN_BIN_DIR:-$HOME/.local/bin}"

command -v claude >/dev/null || echo "warning: 'claude' not found on PATH — install Claude Code first: https://code.claude.com"
command -v python3 >/dev/null || { echo "error: python3 is required"; exit 1; }

mkdir -p "$AGENTS/hooks" "$BIN"
install -m 644 "$SRC/agents/learn.md" "$AGENTS/learn.md"
install -m 755 "$SRC/agents/hooks/safe-bash.py" "$AGENTS/hooks/safe-bash.py"
install -m 755 "$SRC/bin/learn" "$BIN/learn"

# Remove files from the earlier version, when this agent was called "researcher"
# (only if they are ours, so an unrelated agent with that name is left alone)
grep -qs "hooks/safe-bash.py" "$AGENTS/researcher.md" && rm -f "$AGENTS/researcher.md"
grep -qs "Claude Code port of the \`researcher\` agent" "$BIN/researcher" && rm -f "$BIN/researcher"
true

echo "Installed:"
echo "  $AGENTS/learn.md"
echo "  $AGENTS/hooks/safe-bash.py"
echo "  $BIN/learn"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo
     echo "Note: $BIN is not on your PATH. Add this to your ~/.zshrc or ~/.bashrc:"
     echo "  export PATH=\"$BIN:\$PATH\"" ;;
esac

echo
echo "Try it:  learn \"What changed in Python 3.13?\""
