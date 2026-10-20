#!/usr/bin/env bash
# Installs the researcher agent for Claude Code.
#   ~/.claude/agents/researcher.md          subagent definition
#   ~/.claude/agents/hooks/safe-bash.py     safe_bash command blocker
#   ~/.local/bin/researcher                 terminal command
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS="$HOME/.claude/agents"
BIN="${RESEARCHER_BIN_DIR:-$HOME/.local/bin}"

command -v claude >/dev/null || echo "warning: 'claude' not found on PATH — install Claude Code first: https://code.claude.com"
command -v python3 >/dev/null || { echo "error: python3 is required"; exit 1; }

mkdir -p "$AGENTS/hooks" "$BIN"
install -m 644 "$SRC/agents/researcher.md" "$AGENTS/researcher.md"
install -m 755 "$SRC/agents/hooks/safe-bash.py" "$AGENTS/hooks/safe-bash.py"
install -m 755 "$SRC/bin/researcher" "$BIN/researcher"

echo "Installed:"
echo "  $AGENTS/researcher.md"
echo "  $AGENTS/hooks/safe-bash.py"
echo "  $BIN/researcher"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo
     echo "Note: $BIN is not on your PATH. Add this to your ~/.zshrc or ~/.bashrc:"
     echo "  export PATH=\"$BIN:\$PATH\"" ;;
esac

echo
echo "Try it:  researcher \"What changed in Python 3.13?\""
