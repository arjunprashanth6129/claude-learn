# claude-learn

An AI teacher in your terminal, built on [Claude Code](https://code.claude.com). Tell it what you want to learn, optionally hand it your own material (a textbook chapter, notes, a URL), and it teaches you one idea at a time. It checks your conceptual understanding with a quiz and active recall questions, and when you miss one it re-teaches the concept in a different way. The whole lesson is written live into a note in [Obsidian](https://obsidian.md), with math, diagrams, revision notes and every quiz rendered.

Inspired from the learning system by [amosblomqvist/learn](https://github.com/amosblomqvist/learn).

## Two modes

| | `learn` | `study` |
|---|---|---|
| For | Understanding a topic briefly | Deep dives, exams, your own material |
| Starts with | A short plan, then straight into teaching | A pre-quiz to find what you already know, then a plan you approve |
| Each idea | Taught, then one quiz question | Taught in full, then a quiz question |
| After each topic | — | Revision notes and a topic quiz |
| At the end | A final quiz and key takeaways | A final quiz, key takeaways and what to revise next |

```bash
learn "how photosynthesis works"
study "aldehydes, ketones and carboxylic acids" ~/Downloads/chemistry-ch8.pdf
```

## Requirements

- macOS, with [Claude Code](https://code.claude.com) installed and logged in (running `claude` in your terminal should work).
- Python 3, which comes with macOS.
- [Obsidian](https://obsidian.md) (free), with a vault. Lessons are saved in a `Learning` folder inside it.
- An internet connection during install (it downloads parts of the original system).
- For diagrams: [Node.js](https://nodejs.org), Google Chrome, and `rsvg-convert` (`brew install librsvg`).

## Install

```bash
git clone https://github.com/arjunprashanth6129/claude-learn.git
cd claude-learn
./install.sh
```

This installs the system into `~/.claude-learn` and the `learn` and `study` commands into `~/.local/bin`. If the installer says `~/.local/bin` is not on your PATH, add this line to `~/.zshrc` and open a new terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Usage

### Start a session

From any folder:

```bash
learn "what you want to learn"
study "what you want to study" [files or URLs …]
```

Both commands move into `<your vault>/Learning` before starting, and the lesson note opens in Obsidian by itself. They never run in your home folder, where Claude Code would look through Photos, Music and other apps' data and trigger macOS privacy prompts.

The first time, Claude Code asks whether you trust the `Learning` folder; choose **Yes**. If your vault is in `~/Documents`, macOS may also ask once whether Terminal can access Documents. That is the vault itself, so allow it.

### Give it your material

Add files or URLs after the topic, with either command:

```bash
study "electrochemistry" ~/Downloads/ncert-ch2.pdf ~/Notes/electrochem.docx https://example.com/notes
```

- **Files:** PDFs, text and markdown notes, Word documents (converted to text) and images. You can also pass a folder.
- **Drag and drop:** dragging a file from Finder into the Terminal window pastes its path. This works at the start or in the middle of a session (just paste the path into your message).
- **Where they go:** files are copied into `Learning/sources/`, so you can open them in Obsidian next to the lesson.
- **How they're used:** a reader agent reads only the pages the teacher needs. Where your material and the web disagree, the teacher follows your material, since that is what you'll be examined on.

### During a session

Type to the teacher like a normal chat. Quizzes and questions appear as popups:
- Pick an answer with the arrow keys and Enter.
- Choose **I don't know** if you genuinely don't; that's more useful to the teacher than a guess.
- You can attach a note to any answer.

You're graded the moment you answer: ✓ or ✗, the correct answer, and why. Type `/exit` or press Ctrl+D to end.

### The note

Keep Obsidian next to the terminal. The note (`Learning/lessons/learning <topic>.md` or `studying <topic>.md`) fills in as you go:
- **The lesson:** the plan and its dependency map, then a heading per idea, with math in LaTeX and diagrams where a picture helps.
- **Re-teaches:** written in full whenever you miss a quiz.
- **Revision notes:** `## Notes: <topic>` after each topic (study mode).
- **Quizzes:** each one is a foldable block with your answer, the correct answer and the explanation. Ones you got right fold away; misses stay open.
- **Score:** a running score at the bottom, per quiz type.

### Options

```bash
learn --log notes/topic.md           # write the lesson into a note of your choice
learn --no-log                       # no note
learn --research "your question"     # just run the researcher and print a sourced brief
LEARN_DIR=~/Notes/School study "…"   # use a different folder
learn --help
```

## How it works

| Part | What it does | Original |
|---|---|---|
| Teacher | The main Claude Code session. Follows the mode, plus the `teach` skill for how to explain | pi session + `skills/teach` |
| Quizzes | Graded popups with "I don't know" and a note field, graded instantly by `hooks/quiz.py` | `extensions/quiz.ts` |
| Questions | Popups with no right answer (your goal, plan approval, what next) | `extensions/ask-user-question.ts` |
| `reader` | Reads your files and returns exactly what the teacher asks for, with page numbers | new |
| `researcher` | Searches the web (and downloads PDFs) and returns a sourced brief, so the teacher checks facts instead of guessing | `agents/researcher.md` |
| `mermaid-maker`, `svg-maker` | Draw a diagram, look at the rendered image, fix it, save it to `viz/` | `agents/*-maker.md` |
| Lesson note | Mirrors the lesson, your messages and every quiz into the Obsidian note | `extensions/md-log.ts` |
| Lesson gate | Blocks a quiz that has no lesson written before it, or no answer key | new |
| `safe-bash` | Blocks dangerous shell commands (`sudo`, `rm -rf /`, `curl … \| sh`, …) | `safe_bash` |

The `teach` and `visualize` skills and the two diagram agents are downloaded from the original repo when you install, pinned to the version this port was tested with. The skills are used word for word; `learn` mode uses the teach skill without its probe → plan → teach process, since it has its own shorter one. The diagram agents get one change: their pi-only drawing tools are swapped for the `learn-viz` command (`scripts/fetch-upstream.py` shows the exact edits).

Helper agents run as separate, lean `claude -p` processes through the `learn-agent` command (you'll see `Bash(learn-agent reader …)` while one works). Their final message comes back to the teacher, as with pi's subagents.

### Why Haiku teaches by default

On Claude Code 2.1.30x, Sonnet 5.5's hidden thinking can't be turned off. After each quiz answer it tends to work out the next lesson in that thinking and go straight to the next quiz. The teaching then never appears in the terminal or in the note. Haiku 4.5 writes the lesson as visible text after every answer, and costs about a third as much. Sonnet is still available (`LEARN_MODEL=sonnet`), and the lesson gate makes it write the lesson before quizzing. It sometimes takes a few tries, which costs extra.

### Differences from the original

- **Popup.** Claude Code doesn't let you add new popup tools, so quizzes use its built-in question popup. It holds at most 4 options, so a quiz has up to 3 real answers plus "I don't know". The popup also offers "Type something"; if you type your own answer, the teacher grades it on its meaning.
- **Answer key.** The teacher attaches a hidden answer key to each graded question. The gate refuses a quiz without one, so every quiz is graded.
- **Note.** The lesson note is written automatically for every session instead of being linked with `/md-log`, and quizzes are folded into single blocks.

## Cost

| Part | Model |
|---|---|
| Teacher | Haiku, low effort |
| `reader`, `researcher` | Haiku, low effort |
| `mermaid-maker`, `svg-maker` | Sonnet, low effort (they must check their own picture is right) |

To keep each message small, the teacher runs with only its own instructions (not Claude Code's coding instructions) and two tools. It also loads:
- no MCP servers, skills, memory or CLAUDE.md files
- no background summaries or auto-mode permission checks

In testing, at API prices (on a Claude subscription this comes out of your plan's usage limits instead):

| Session | Teacher cost |
|---|---|
| `learn`: 2 ideas, 2 re-teaches, final quiz | about $0.08 |
| `study`: outline of a PDF, pre-quiz, 2 ideas, topic notes and quiz, final quiz | about $0.15 |
| A researcher fact check (extra) | about $0.13 |
| A diagram (extra) | about $0.05 |

Each message re-sends the conversation so far, so longer lessons cost more per message towards the end. Each helper-agent run stops at $0.30 (change with `LEARN_BUDGET_USD=0.15`).

```bash
LEARN_MODEL=sonnet study "…"     # stronger teacher, about 3x the cost (see above)
LEARN_EFFORT=medium learn "…"    # more careful, more expensive
```

## Customizing

- **Session shape:** `system/mode-learn.md` and `system/mode-study.md` (how many ideas, when to quiz, what goes in the notes).
- **Shared rules:** `system/teacher.md` (quiz protocol, note structure, tool mapping).
- **How you're taught:** `~/.claude-learn/skills/teach/SKILL.md`. Running `./install.sh` again downloads a fresh copy over your edits.
- **Agents:** `agents/*.md`.

Run `./install.sh` after editing the repo's files.

## Updating

```bash
cd claude-learn
git pull
./install.sh
```

## Uninstall

```bash
rm -rf ~/.claude-learn ~/.local/bin/learn ~/.local/bin/study
```

Your lessons and sources stay in your vault's `Learning` folder.

## Credits

- Learning system, teaching method, agents and diagram tools: [amosblomqvist/learn](https://github.com/amosblomqvist/learn).
- Researcher agent and safe_bash: [pi-interactive-subagents](https://github.com/amosblomqvist/pi-interactive-subagents) (MIT), a fork of [HazAT/pi-interactive-subagents](https://github.com/HazAT/pi-interactive-subagents).
- Video: [How I Use AI to Learn Things](https://www.youtube.com/watch?v=kzcI5F4tGiU) by Eero Alvar.

## License

MIT for everything in this repository. See [LICENSE](LICENSE). The `teach` and `visualize` skills and the diagram agents are not part of this repository. The installer downloads them from [amosblomqvist/learn](https://github.com/amosblomqvist/learn), which has no license file, so they stay under their author's terms.
