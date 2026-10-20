#!/usr/bin/env python3
"""safe_bash for Claude Code: a PreToolUse hook on Bash that blocks the same
dangerous patterns as pi-interactive-subagents' safe-bash.ts."""
import json
import re
import sys

DANGEROUS_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?(-[a-zA-Z]*r[a-zA-Z]*\s+)?(\/|~\/?\s|~\/?\b)",
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?(-[a-zA-Z]*f[a-zA-Z]*\s+)?(\/|~\/?\s|~\/?\b)",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",
    r">\s*\/dev\/[sh]d[a-z]",
    r"\bchmod\s+(-[a-zA-Z]+\s+)?777\s+\/",
    r"\bchown\s+(-[a-zA-Z]+\s+)?root",
    r"\bcurl\s.*\|\s*(ba)?sh",
    r"\bwget\s.*\|\s*(ba)?sh",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+0\b",
    r"\bkill\s+-9\s+1\b",
    r"\bkillall\b",
]

data = json.load(sys.stdin)
command = (data.get("tool_input") or {}).get("command", "").replace("\\\n", " ")
for pattern in DANGEROUS_PATTERNS:
    if re.search(pattern, command):
        print(f"Command blocked by safe_bash: matches dangerous pattern /{pattern}/", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
