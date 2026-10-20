#!/usr/bin/env python3
"""Download the original learn system's skills and diagram agents and adapt them
for Claude Code.

These files come from github.com/amosblomqvist/learn, which has no license, so
they are not redistributed in this repo. The installer fetches them straight
from the original, pinned to the commit this port was built and tested against.

Usage: fetch-upstream.py <install-dir>
"""
import os
import re
import sys
import urllib.request

REPO = "amosblomqvist/learn"
COMMIT = "7cfd8942f82ab9476e63572387e1fe9bcea5082c"
RAW = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/"


def fetch(path):
    with urllib.request.urlopen(RAW + path, timeout=120) as r:
        return r.read().decode("utf-8")


def replace(text, old, new, label):
    if old not in text:
        sys.exit(f"fetch-upstream: could not adapt {label} (upstream text changed): {old[:60]!r}")
    return text.replace(old, new)


def sub(text, pattern, new, label):
    out, n = re.subn(pattern, new, text)
    if n == 0:
        sys.exit(f"fetch-upstream: could not adapt {label} (upstream text changed): {pattern[:60]!r}")
    return out


def port_maker(kind):
    """pi's write_*/edit_*/render_* tools -> the learn-viz command (via Bash) + Read."""
    name = f"{kind}-maker"
    label = f"agents/{name}.md"
    _, head, body = fetch(label).split("---", 2)
    desc = re.search(r"^description: (.*)$", head, re.M).group(1)
    front = f"---\nname: {name}\ndescription: {desc}\ntools: Bash, Read\nmodel: sonnet\neffort: medium\n---\n"
    body = replace(body,
        f"You have exactly three authoring tools — `write_{kind}`, `edit_{kind}`, `render_{kind}` — plus `read`. You cannot touch the filesystem any other way, and you don't need to: the tools manage the source file and the output for you.",
        f"You have exactly one authoring tool — the `learn-viz {kind}` command, run through Bash — plus `Read`. Use Bash ONLY to run `learn-viz`; you cannot touch the filesystem any other way, and you don't need to: `learn-viz` manages the source file and the output for you.\n\n"
        f"- **Write + render a preview** — pass the complete source on stdin:\n  ```\n  learn-viz {kind} <<'EOF'\n  <complete source>\n  EOF\n  ```\n  It prints the path of the preview PNG. **`Read` that PNG to look at it.**\n"
        f"- **Edit** — run the same command again with the corrected complete source (the last source is kept, so this replaces it).\n"
        f"- **Publish** — `learn-viz {kind} --save-as <short-kebab-topic>` with no stdin re-renders the last source and publishes it.",
        label)
    body = replace(body, f"`render_{kind}` returns the image inline — actually look at it.",
                   f"`learn-viz {kind}` prints the preview path — `Read` it and actually look at it.", label)
    body = sub(body, rf"with `write_{kind}\(\{{ source \}}\)`", f"with `learn-viz {kind} <<'EOF' … EOF`", label)
    body = sub(body, rf"with `render_{kind}\(\{{\}}\)` \(no `save_as`\)\. Look at the returned image\.",
               f"— the same `learn-viz {kind}` call renders it. `Read` the preview PNG it prints and look at it.", label)
    body = sub(body, rf"with `edit_{kind}\(\{{ old_text, new_text \}}\)` and re-render",
               f"by running `learn-viz {kind}` again with the corrected source", label)
    body = replace(body, f"If `render_{kind}` returns an error", f"If `learn-viz {kind}` prints an error", label)
    body = replace(body, f"call `render_{kind}({{ save_as: \"<short-kebab-topic>\" }})`",
                   f"run `learn-viz {kind} --save-as <short-kebab-topic>`", label)
    body = replace(body, f"returned by render_{kind}", "printed by learn-viz", label)
    body = replace(body, "Confirm the published image one last time.",
                   "`Read` the published image to confirm it one last time.", label)
    return front + body


def write(dest, rel, content):
    path = os.path.join(dest, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip())
    dest = sys.argv[1]
    try:
        # The skills are used word for word; system/teacher.md maps their tool names.
        write(dest, "skills/teach/SKILL.md", fetch("skills/teach/SKILL.md"))
        write(dest, "skills/visualize/SKILL.md", fetch("skills/visualize/SKILL.md"))
        write(dest, "agents/mermaid-maker.md", port_maker("mermaid"))
        write(dest, "agents/svg-maker.md", port_maker("svg"))
    except OSError as e:
        sys.exit(f"fetch-upstream: download failed ({e}). Check your internet connection and run ./install.sh again.")
    print(f"  fetched from github.com/{REPO} @ {COMMIT[:7]}")


if __name__ == "__main__":
    main()
