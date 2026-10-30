#!/usr/bin/env python3
"""md-log — mirror the session into an Obsidian note as you learn.

Claude Code port of extensions/md-log.ts from amosblomqvist/learn. The note is
meant to be read rendered (Obsidian), so lesson text with $...$ math, mermaid,
code blocks and ![[viz-...png]] embeds renders natively.

What the note holds:
  - the lesson itself (the teacher's message text), as plain markdown
  - your messages                   > [!quote] You
  - each quiz, live while you answer, then one foldable block with the result,
    your answer, the correct answer and the explanation (collapsed when right)
  - a running score at the end
Tool calls (subagents, file reads, ...) are left out.

Runs as a Claude Code hook (UserPromptSubmit, PreToolUse/PostToolUse on
AskUserQuestion, Stop). The note comes from $LEARN_LOG_FILE, set by `learn`.

Claude Code writes the transcript slightly after hooks fire, so instead of
appending, each event re-renders this session's part of the note from the
transcript (idempotent), once now and a few more times shortly after in a
detached process. Anything the note held before the session is kept.
"""
import fcntl
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from quiz import GRADED, answer_key, grade, is_quiz, kind, label  # noqa: E402

QA_TOOL = "AskUserQuestion"
RETRY_DELAYS = (0.7, 2.0, 5.0, 12.0, 25.0)


# --- Formatting ---

def callout(kind_, title, body_lines, fold=""):
    lines = [f"> [!{kind_}]{fold} {title}"]
    for line in body_lines:
        lines.append(">" if line == "" else f"> {line}")
    return "\n".join(lines)


def user_block(text):
    return callout("quote", "You", text.split("\n"))


def one_line(text, limit=140):
    t = " ".join(str(text).split())
    return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"


def question_callout(q):
    """A question as it is being asked (open, no answer yet)."""
    body = (q.get("question") or "").split("\n")
    opts = q.get("options") or []
    if opts:
        body.append("")
        body += [f"{i + 1}. {o.get('label', '')}" for i, o in enumerate(opts)]
    return callout("question", label(q), body)


def option_lines(q, picked, correct):
    out = []
    for i, o in enumerate(q.get("options") or []):
        lab = o.get("label", "")
        marks = (" ✓" if lab in correct else "") + (" ← your answer" if lab in picked else "")
        out.append(f"{i + 1}. {lab}{marks}")
    others = [p for p in picked if p not in [o.get("label", "") for o in q.get("options") or []]]
    out += [f"Your answer: {p}" for p in others if p]
    return out


def note_lines(note):
    if not note:
        return []
    lines = str(note).split("\n")
    return ["", f"Your note: {lines[0]}"] + lines[1:]


def answered_callout(q, answer, note, key=None):
    """One foldable block per answered question: result in the title, details inside."""
    name = label(q)
    title_q = one_line(q.get("question", ""))
    if answer is None:
        return callout("warning", f"{name} skipped · {title_q}", (q.get("question") or "").split("\n"), "-")
    g = grade(q, answer, key) if is_quiz(q) else None
    picked = [a.strip() for a in str(answer).split(", ")] if q.get("multiSelect") else [str(answer).strip()]
    if g is None:
        if is_quiz(q):  # quiz without an answer key: show the pick, the teacher grades in the lesson
            return callout("example", f"{name} · {title_q}", option_lines(q, picked, []) + note_lines(note), "-")
        return callout("example", f"{one_line(q.get('question', ''), 80)} → {one_line(', '.join(picked), 60)}",
                       note_lines(note)[1:] or [], "-")
    if g["dont_know"]:
        kind_, mark, fold = "question", "?", "+"
    elif g["other"]:
        kind_, mark, fold = "example", "✎", "+"
    elif g["is_correct"]:
        kind_, mark, fold = "success", "✓", "-"
    else:
        kind_, mark, fold = "failure", "✗", "+"
    full = q.get("question") or ""
    body = (full.split("\n") + [""] if one_line(full) != " ".join(full.split()) else []) + option_lines(q, picked, g["correct"])
    body += note_lines(note)
    if g["explanation"]:
        body += [""] + g["explanation"].split("\n")
    return callout(kind_, f"{mark} {name} · {title_q}", body, fold)


def score_callout(results):
    """results: list of (kind, grade) for every graded answer this session."""
    if not results:
        return ""
    parts = []
    for k, name in GRADED.items():
        gs = [g for kk, g in results if kk == k]
        if not gs:
            continue
        right = sum(1 for g in gs if g["is_correct"])
        dk = sum(1 for g in gs if g["dont_know"])
        parts.append(f"**{name}** {right}/{len(gs)}" + (f" ({dk} I don't know)" if dk else ""))
    return callout("info", "Score", [" · ".join(parts)])


# --- Transcript -> blocks ---

def as_questions(value):
    """AskUserQuestion's `questions`, tolerating a JSON-encoded string."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return [q for q in value or [] if isinstance(q, dict)] if isinstance(value, list) else []


# System-injected text in user turns (reminders, background-task notices) is not the learner's.
INJECTED_RE = re.compile(r"<(system-reminder|task-notification)>[\s\S]*?</\1>")


def clean_user_text(text):
    text = INJECTED_RE.sub("", text or "").strip()
    if not text or text.startswith(("<command-", "<local-command", "Caveat:", "[Request interrupted")):
        return ""
    return text


def parse_answers(entry, questions):
    """Return {question_text: (answer|None, note)} from an AskUserQuestion tool_result entry."""
    out = {}
    tur = entry.get("toolUseResult")
    if isinstance(tur, dict):
        answers = tur.get("answers") or {}
        annotations = tur.get("annotations") or {}
        for q in questions:
            qt = q.get("question", "")
            ann = annotations.get(qt) or {}
            out[qt] = (answers.get(qt), ann.get("notes") if isinstance(ann, dict) else None)
        if answers:
            return out
    # Fallback: parse the tool_result text, e.g.  "Question"="Answer"
    text = ""
    for c in entry.get("message", {}).get("content") or []:
        if isinstance(c, dict) and c.get("type") == "tool_result":
            body = c.get("content")
            text = body if isinstance(body, str) else " ".join(x.get("text", "") for x in body or [] if isinstance(x, dict))
    pairs = dict(re.findall(r'"([^"]+)"\s*=\s*"([^"]*)"', text))
    for q in questions:
        qt = q.get("question", "")
        out[qt] = (pairs.get(qt), None)
    return out


def render(transcript_path, pending_tool=None, last_message=None, pending_prompt=None):
    blocks, prose = [], []
    asked = {}    # tool_use_id -> questions
    keys = {}     # tool_use_id -> quiz answer key
    pending = {}  # tool_use_id -> index of its live question block(s) in `blocks`
    results = []  # (kind, grade) per graded answer, for the score

    def flush():
        if prose:
            blocks.append("\n\n".join(prose))
            prose.clear()

    entries = []
    if transcript_path and os.path.exists(transcript_path):
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    for e in entries:
        if e.get("isSidechain") or e.get("isMeta"):
            continue
        msg = e.get("message") if isinstance(e.get("message"), dict) else None
        if not msg:
            continue
        content = msg.get("content")
        if e.get("type") == "user":
            if isinstance(content, str):
                text = clean_user_text(content)
                if text:
                    flush()
                    blocks.append(user_block(text))
                continue
            texts = []
            for c in content or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_result" and c.get("tool_use_id") in asked:
                    flush()
                    tid = c["tool_use_id"]
                    qs, key = asked[tid], keys.get(tid)
                    answers = parse_answers(e, qs) if not c.get("is_error") or "answered" in str(c.get("content")) else {}
                    done = []
                    for q in qs:
                        a, note = answers.get(q.get("question", ""), (None, None))
                        if c.get("is_error") and a is None and "doesn't want to proceed" not in str(c.get("content")):
                            continue  # rejected by a hook/validation and re-asked: not a real question
                        done.append(answered_callout(q, a, note, key))
                        g = grade(q, a, key) if is_quiz(q) else None
                        if g and not g["other"]:
                            results.append((kind(q), g))
                    start, n = pending.pop(tid, (None, 0))
                    if start is not None:  # replace the live question with its answered block
                        blocks[start:start + n] = done
                        for other, (st, k) in pending.items():
                            if st > start:
                                pending[other] = (st + len(done) - n, k)
                    else:
                        blocks += done
                elif c.get("type") == "text":
                    t = clean_user_text(c.get("text", ""))
                    if t:
                        texts.append(t)
            if texts:
                flush()
                blocks.append(user_block("\n".join(texts)))
        elif e.get("type") == "assistant":
            for c in content or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and c.get("text", "").strip():
                    prose.append(c["text"].strip())
                elif c.get("type") == "tool_use" and c.get("name") == QA_TOOL:
                    flush()
                    qs = as_questions((c.get("input") or {}).get("questions"))
                    asked[c.get("id")] = qs
                    keys[c.get("id")] = answer_key(c.get("input"))
                    pending[c.get("id")] = (len(blocks), len(qs))
                    blocks += [question_callout(q) for q in qs]

    # The hook can fire before Claude Code has written the newest events.
    prompt = clean_user_text(pending_prompt or "")
    if prompt and not (blocks and blocks[-1] == user_block(prompt)):
        flush()
        blocks.append(user_block(prompt))
    if pending_tool and pending_tool.get("id") not in asked:
        flush()
        blocks += [question_callout(q) for q in as_questions(pending_tool.get("questions"))]
    if last_message and last_message.strip():
        seen = "\n\n".join(blocks + prose)
        if last_message.strip() not in seen:
            prose.append(last_message.strip())
    flush()
    # Questions that were rejected (validation error / lesson gate) and never answered
    # are left as live blocks only if they are the latest thing on screen.
    for tid, (start, n) in sorted(pending.items(), key=lambda kv: -kv[1][0]):
        if start + n < len(blocks):
            del blocks[start:start + n]
    score = score_callout(results)
    return "\n\n".join(blocks + ([score] if score else []))


# --- File section management ---

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ".state")
LEGACY_MARK = re.compile(r"%% learn md-log · session .*? %%")


def write_log(log_file, session_id, body):
    """Write this session's lesson into the note, keeping whatever the note held before it.

    What was there before the session started is remembered in a small state file
    (not as a marker in the note), and the note is rewritten in place like the
    original's writeFileSync so Obsidian keeps live-updating the open note.
    """
    key = hashlib.sha1(os.path.abspath(log_file).encode()).hexdigest()[:16]
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    state_path = os.path.join(STATE_DIR, key + ".json")
    with open(os.path.join(STATE_DIR, key + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = open(log_file, encoding="utf-8").read() if os.path.exists(log_file) else ""
        try:
            state = json.load(open(state_path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        if state.get("session") == session_id:
            prefix = state.get("prefix", "")
        else:
            prefix = LEGACY_MARK.split(current, 1)[0].rstrip()
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"session": session_id, "file": os.path.abspath(log_file), "prefix": prefix}, f)
        new = (prefix + "\n\n" + body if prefix else body) + "\n"
        if new != current:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(new)


def sync(data, log_file):
    pending = None
    if data.get("hook_event_name") == "PreToolUse" and data.get("tool_name") == QA_TOOL:
        pending = {"id": data.get("tool_use_id"), "questions": (data.get("tool_input") or {}).get("questions")}
    last = data.get("last_assistant_message") if data.get("hook_event_name") == "Stop" else None
    prompt = data.get("prompt") if data.get("hook_event_name") == "UserPromptSubmit" else None
    body = render(data.get("transcript_path"), pending, last, prompt)
    if body:
        write_log(log_file, data.get("session_id", "unknown"), body)


def main():
    log_file = os.environ.get("LEARN_LOG_FILE")
    if not log_file:
        return
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    try:
        sync(data, log_file)
    except Exception:
        pass
    # Re-render shortly after, once Claude Code has flushed the transcript.
    if os.fork() != 0:
        return
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    # By now the prompt is in the transcript; re-adding it could duplicate it.
    data.pop("prompt", None)
    for delay in RETRY_DELAYS:
        time.sleep(delay)
        try:
            sync(data, log_file)
        except Exception:
            pass
    os._exit(0)


if __name__ == "__main__":
    main()
