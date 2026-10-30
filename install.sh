#!/usr/bin/env bash
# Installs learn: an AI teacher for your terminal, built on Claude Code.
#   ~/.claude-learn/          the system (teacher instructions, agents, hooks, renderer,
#                             plus the skills and diagram agents downloaded from amosblomqvist/learn)
#   ~/.local/bin/learn, study the commands (links into ~/.claude-learn)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${LEARN_HOME:-$HOME/.claude-learn}"
BIN="${LEARN_BIN_DIR:-$HOME/.local/bin}"

command -v claude >/dev/null || echo "warning: 'claude' not found on PATH — install Claude Code first: https://code.claude.com"
command -v python3 >/dev/null || { echo "error: python3 is required"; exit 1; }

echo "Installing to $DEST"
mkdir -p "$DEST" "$BIN"
for item in bin agents hooks scripts system LICENSE README.md package.json; do
  rm -rf "$DEST/$item"
  cp -R "$SRC/$item" "$DEST/$item"
done
chmod +x "$DEST/bin/"* "$DEST/hooks/"*.py
ln -sf "$DEST/bin/learn" "$BIN/learn"
ln -sf "$DEST/bin/study" "$BIN/study"

# The teach/visualize skills and diagram agents come from the original repo,
# which has no license, so they are downloaded from there rather than shipped here.
echo "Downloading the teaching skills and diagram agents from amosblomqvist/learn…"
rm -rf "$DEST/skills"
python3 "$DEST/scripts/fetch-upstream.py" "$DEST"

# Diagram rendering: mermaid-cli drives your installed Chrome (no Chromium download).
if command -v npm >/dev/null; then
  echo "Installing the diagram renderer (mermaid-cli)…"
  (cd "$DEST" && PUPPETEER_SKIP_DOWNLOAD=1 npm install --silent --no-audit --no-fund >/dev/null 2>&1) \
    && echo "  done" \
    || echo "  skipped (npm install failed) — diagrams will fall back to npx on first use"
else
  echo "note: npm not found — install Node.js for Mermaid diagrams (https://nodejs.org)"
fi
[ -e "/Applications/Google Chrome.app" ] || [ -e "/Applications/Chromium.app" ] \
  || echo "note: Google Chrome not found — Mermaid diagrams need it"
command -v rsvg-convert >/dev/null || command -v magick >/dev/null \
  || echo "note: rsvg-convert not found — for SVG diagrams run: brew install librsvg"

# Remove files from earlier versions of this project (only if they are ours).
grep -qs "hooks/safe-bash.py" "$HOME/.claude/agents/learn.md" && rm -f "$HOME/.claude/agents/learn.md"
grep -qs "hooks/safe-bash.py" "$HOME/.claude/agents/researcher.md" && rm -f "$HOME/.claude/agents/researcher.md"
grep -qs "safe_bash for Claude Code" "$HOME/.claude/agents/hooks/safe-bash.py" && rm -f "$HOME/.claude/agents/hooks/safe-bash.py"
rmdir "$HOME/.claude/agents/hooks" 2>/dev/null || true
grep -qs "Claude Code port of the \`researcher\` agent" "$BIN/researcher" && rm -f "$BIN/researcher"
true

echo
echo "Installed: $BIN/learn and $BIN/study"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo
     echo "Note: $BIN is not on your PATH. Add this to your ~/.zshrc or ~/.bashrc, then open a new terminal:"
     echo "  export PATH=\"$BIN:\$PATH\"" ;;
esac

echo
echo "Try it:  learn \"how photosynthesis works\""
echo "         study \"electrochemistry\" ~/Downloads/chapter.pdf"
