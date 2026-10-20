# claude-learn

`learn` is an AI teacher in your terminal, built on [Claude Code](https://code.claude.com). Tell it what you want to learn. It finds out what you already know with quick quizzes, proposes a lesson plan, then teaches you step by step, checking each step with a quiz before moving on. The whole lesson is mirrored into a markdown file you can read in [Obsidian](https://obsidian.md) with math, diagrams and images rendered.

It is a port of the AI learning system from [amosblomqvist/learn](https://github.com/amosblomqvist/learn), shown in the video [How I Use AI to Learn Things](https://www.youtube.com/watch?v=kzcI5F4tGiU). The original runs on [pi](https://github.com/badlogic/pi-mono). This version runs the same teaching method, the same agents and the same lesson log on Claude Code, using Claude Sonnet.

## Requirements

- [Claude Code](https://code.claude.com), installed and logged in. Running `claude` in your terminal should work.
- Python 3, which comes with macOS.
- An internet connection during install (it downloads parts of the original system).
- For diagrams: [Node.js](https://nodejs.org), Google Chrome, and `rsvg-convert` (`brew install librsvg`).
- To read lessons rendered: [Obsidian](https://obsidian.md) (free). Optional — the lesson file is plain markdown.

## Install

```bash
git clone https://github.com/arjunprashanth6129/claude-learn.git
cd claude-learn
./install.sh
```

This installs the system into `~/.claude-learn` and the `learn` command into `~/.local/bin`. If the installer says `~/.local/bin` is not on your PATH, add this line to `~/.zshrc` and open a new terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Usage

### 1. Make a folder for your learning (once)

```bash
mkdir -p ~/Learning
```

In Obsidian, choose **Open folder as vault** and pick `~/Learning`. Lessons and diagrams will be saved here.

### 2. Start a session

```bash
cd ~/Learning
learn
```

Or start with what you want to learn:

```bash
learn "I want to understand how backtesting works in quantitative finance"
```

The first time you use a folder, Claude Code asks whether you trust it. Choose **Yes**.

### 3. Learn

Type to the teacher like a normal chat. A session goes through three phases:

1. **Probe.** It quizzes you to find exactly where your knowledge runs out, and asks what you want to get out of the topic. Quizzes appear as popups. Pick an answer with the arrow keys and Enter, or choose **I don't know** if you genuinely don't know (that's more useful to it than a guess). You can attach a note to any answer.
2. **Plan.** It researches the topic, then shows you a plan and a map of how the ideas depend on each other. Say "go" or ask for changes.
3. **Teach.** It builds the topic one idea at a time — why it's needed, what it is, how it connects to what you know — and quizzes you on each before moving on.

Keep the lesson file open in Obsidian next to the terminal. It updates as you go: `lessons/<date>-<topic>.md`.

Type `/exit` or press Ctrl+D to end the session. To continue a lesson later, run `claude --resume` in the same folder.

### Options

```bash
learn --log notes/backtesting.md     # mirror into a file of your choice
learn --no-log                       # no lesson file
learn --research "your question"     # just run the researcher and print a sourced brief
learn --help
```

## What's inside

| Part | What it does | Original |
|---|---|---|
| Teacher | The main session. Follows the `teach` skill: probe → plan → teach | pi session + `skills/teach` |
| Quizzes | Graded multiple-choice popups with "I don't know" and a note field | `extensions/quiz.ts` |
| Questions | Popups for questions with no right answer (your goal, what next) | `extensions/ask-user-question.ts` |
| `researcher` | Searches the web and returns a sourced brief, so the teacher checks facts instead of guessing | `agents/researcher.md` |
| `mermaid-maker` | Draws dependency graphs and flowcharts, looks at the image, fixes it, saves it to `viz/` | `agents/mermaid-maker.md` |
| `svg-maker` | Draws geometric pictures (number lines, vectors, plots) the same way | `agents/svg-maker.md` |
| Lesson log | Mirrors your messages, the lessons and every quiz with your answer into a markdown file | `extensions/md-log.ts` |
| `safe-bash` | Blocks dangerous shell commands (`sudo`, `rm -rf /`, `curl … \| sh`, …) | `safe_bash` |

The `teach` and `visualize` skills and the two diagram agents are downloaded from the original repo when you install, pinned to the version this port was tested with. The skills are used word for word. The diagram agents get one change: their pi-only drawing tools are swapped for the `learn-viz` command (`scripts/fetch-upstream.py` shows the exact edits). The teacher also gets a short extra section that maps the original's tool names to Claude Code's (`system/teacher.md`).

### Differences from the original

Claude Code doesn't let you add new popup tools, so the original `quiz` tool is replaced by Claude Code's built-in question popup:

- **Grading.** The original's quiz tool graded your answer itself. Here the teacher decides the correct answer before asking and grades your pick right after (`✓ Correct.` / `✗ Incorrect — correct answer: …`).
- **Number of options.** The popup holds at most 4 options, so a quiz has up to 3 real answers plus "I don't know".
- **Typed answers.** The popup always offers "Other" for typing your own answer. The teacher grades it on its meaning.

Everything else works as in the original: subagents run in the background instead of in tmux panes, and the lesson log is written automatically for every session instead of being linked with `/md-log`.

## Cost

Everything runs on Claude Sonnet: the teacher at medium effort (the original's `thinking: medium`), and the researcher and diagram agents at medium effort too. To keep usage low, `learn` starts Claude Code with only the 8 tools the system uses. It loads no MCP servers (like Notion or Google Drive) and no other skills, so each message carries much less context than a normal Claude Code session.

In testing:

| Step | Cost |
|---|---|
| A teaching message plus a quiz | about $0.02–0.03 |
| A fact check with the researcher | about $0.10–0.15 |
| A diagram | about $0.05 |

A full lesson is many messages, and each message re-sends the conversation so far, so long sessions cost more than these numbers add up to. If you use Claude Code with a Claude subscription, sessions count against your plan's usage limits instead of costing money directly.

To change the model or effort:

```bash
LEARN_MODEL=haiku learn          # cheaper, but follows the teaching method less carefully
LEARN_EFFORT=low learn           # less thinking per message
```

`learn --research` stops at $0.50 per run (change with `LEARN_BUDGET_USD=0.25`).

## Customizing

The teaching method was written by the original author for their own learning. To change how you're taught, edit `~/.claude-learn/skills/teach/SKILL.md` (note that running `./install.sh` again downloads a fresh copy over your edits). The researcher's instructions are in `agents/researcher.md`, and the Claude Code adapter is in `system/teacher.md`. Run `./install.sh` after editing those.

## Updating

```bash
cd claude-learn
git pull
./install.sh
```

The installer also removes files from earlier versions of this project (the standalone `researcher` command).

## Uninstall

```bash
rm -rf ~/.claude-learn ~/.local/bin/learn
```

## Credits

- Learning system, teaching method, agents and diagram tools: [amosblomqvist/learn](https://github.com/amosblomqvist/learn).
- Researcher agent and safe_bash: [pi-interactive-subagents](https://github.com/amosblomqvist/pi-interactive-subagents) (MIT), a fork of [HazAT/pi-interactive-subagents](https://github.com/HazAT/pi-interactive-subagents).
- Video: [How I Use AI to Learn Things](https://www.youtube.com/watch?v=kzcI5F4tGiU) by Eero Alvar.

## License

MIT for everything in this repository. See [LICENSE](LICENSE). The `teach` and `visualize` skills and the diagram agents are not part of this repository. The installer downloads them from [amosblomqvist/learn](https://github.com/amosblomqvist/learn), which has no license file, so they stay under their author's terms.
