# claude-learn

`learn` is a web research agent for [Claude Code](https://code.claude.com) that you run from your terminal. Ask it a question and it searches the web, reads the best sources, and gives you back a short brief with citations.

It is a port of the `researcher` agent from [amosblomqvist/learn](https://github.com/amosblomqvist/learn), the AI learning system shown in [How I Use AI to Learn Things](https://www.youtube.com/watch?v=kzcI5F4tGiU). The original runs on [pi](https://github.com/badlogic/pi-mono) with [pi-interactive-subagents](https://github.com/amosblomqvist/pi-interactive-subagents). This version keeps the same instructions, tools, output format and medium thinking level, and runs on Claude Haiku, the cheapest Claude model.

```
$ learn "What is the current recommended way to define custom subagents in Claude Code, and which frontmatter fields are supported?"
learn · haiku · effort medium
  web_search  Claude Code custom subagents frontmatter fields definition
  web_search  Claude Code subagents configuration documentation
  web_fetch   https://docs.anthropic.com/en/docs/claude-code/subagents
  web_fetch   https://code.claude.com/docs/en/subagents
done · 5 turns · $0.1289

## Summary
Custom subagents in Claude Code are defined as Markdown files with YAML frontmatter stored in
`.claude/agents/` (project) or `~/.claude/agents/` (user-level). Only `name` and `description`
are required; the Markdown body below the frontmatter serves as the subagent's system prompt. ...
```

## Requirements

- [Claude Code](https://code.claude.com), installed and logged in. Running `claude` in your terminal should work.
- Python 3, which comes with macOS and most Linux systems.

## Install

```bash
git clone https://github.com/arjunprashanth6129/claude-learn.git
cd claude-learn
./install.sh
```

The installer copies three files into place:

| File | Installed to | What it does |
|---|---|---|
| `bin/learn` | `~/.local/bin/learn` | The terminal command |
| `agents/learn.md` | `~/.claude/agents/learn.md` | The agent's instructions and settings |
| `agents/hooks/safe-bash.py` | `~/.claude/agents/hooks/safe-bash.py` | Blocks dangerous shell commands |

If the installer says `~/.local/bin` is not on your PATH, add this line to `~/.zshrc` (or `~/.bashrc`) and open a new terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Usage

### From the terminal

```bash
learn "your question"
```

While it works you see each search and page it reads, and when it finishes it prints the brief. The progress lines go to stderr and the brief goes to stdout, so you can save just the brief to a file:

```bash
learn "How does HTTP/3 differ from HTTP/2?" > http3.md
```

You can also pipe a question in:

```bash
echo "Best practices for Postgres connection pooling" | learn
```

The agent starts with no knowledge of your conversation or files, so put all the context it needs in the question. "Compare Vercel and Netlify for a small Next.js site with ~10k monthly visitors" will get a better answer than "which host should I use?".

### Inside Claude Code

The same agent is also available to Claude Code itself. Start a new Claude Code session after installing and ask for it by name:

```
use the learn agent to find out how React Server Components handle caching
```

Claude Code sends the question to the agent, which runs in its own context and passes back the brief.

## Output format

The agent is told to answer with four sections: **Summary**, **Findings** (numbered, each with a source link), **Sources** (which sources it kept and dropped, and why) and **Gaps** (what it couldn't answer). Haiku usually follows this, but sometimes uses its own headings or leaves out Sources and Gaps. If you need the exact format every time, switch the model to `sonnet` (see [Customizing](#customizing)), which costs more.

## Cost

Each run uses Claude Haiku at medium effort, with a hard spending cap of **$0.50 per run**. In testing, a question cost **$0.13 to $0.38**. Most of that comes from the size of the web search results, not from the model.

To change the cap for a single run:

```bash
LEARN_BUDGET_USD=0.25 learn "your question"
```

If a run reaches the cap it stops early and you get no brief, so don't set it too low.

If you use Claude Code with a Claude subscription instead of an API key, runs count against your plan's usage limits rather than costing money directly.

## How it maps to the original

| Original (pi) | This port (Claude Code) |
|---|---|
| `name: researcher` | `learn` |
| `model: openrouter/z-ai/glm-5.3` | `haiku` |
| `thinking: medium` | `effort: medium` |
| `tools: web_search, web_fetch, safe_bash` | `WebSearch`, `WebFetch`, `Bash` + the safe_bash hook |
| `system-prompt: append` | The agent's instructions are added on top of Claude Code's own (`--append-system-prompt-file`) |
| `auto-exit: true` | Runs with `claude -p`, so it stops on its own and its last message is the brief |

The instructions in `agents/learn.md` are the original's word for word. The only edits are the tool names (`web_search` → `WebSearch`, `web_fetch` → `WebFetch`).

**safe_bash.** In the original, `safe_bash` is a normal shell that refuses a fixed list of dangerous commands (`sudo`, `mkfs`, `killall`, `curl ... | sh` and so on). `agents/hooks/safe-bash.py` checks every shell command the agent tries against the same list, copied pattern for pattern, and blocks any match. Because it is an exact copy, it also keeps the original's gaps (for example, `rm -rf ~/` is not caught). The agent has no tools for editing files.

## Customizing

- **Model and effort:** edit `MODEL` and `EFFORT` at the top of `bin/learn` for the terminal command, and `model:` / `effort:` in `agents/learn.md` for use inside Claude Code. Then run `./install.sh` again.
- **Instructions or output format:** edit the text below the `---` block in `agents/learn.md`. The terminal command reads this same file, so one edit changes both.

## Updating

```bash
cd claude-learn
git pull
./install.sh
```

If you installed the earlier version, when the command was called `researcher`, the installer removes the old `researcher` files for you.

## Uninstall

```bash
rm ~/.local/bin/learn ~/.claude/agents/learn.md ~/.claude/agents/hooks/safe-bash.py
```

## Credits

- Agent design and prompt: [amosblomqvist/learn](https://github.com/amosblomqvist/learn) and [pi-interactive-subagents](https://github.com/amosblomqvist/pi-interactive-subagents) (MIT), which is a fork of [HazAT/pi-interactive-subagents](https://github.com/HazAT/pi-interactive-subagents).
- Video: [How I Use AI to Learn Things](https://www.youtube.com/watch?v=kzcI5F4tGiU) by Eero Alvar.

## License

MIT. See [LICENSE](LICENSE).
