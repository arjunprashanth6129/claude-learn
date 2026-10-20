#!/usr/bin/env python3
"""md-log — mirror the session to a markdown file for comfortable reading.

Claude Code port of extensions/md-log.ts from amosblomqvist/learn. The linked
.md file is meant to be viewed rendered (e.g. in Obsidian), so lesson text with
$...$ math, mermaid, code blocks and ![[viz-...png]] embeds renders natively.

Captures only reading-relevant content:
  - user prompts                       > [!quote] YOU
  - assistant text (lesson prose)      > [!abstract] CLAUDE
  - quiz / question Q&A blocks         > [!question] Quiz | Question, then the answer
Other tools (bash, read, web, subagents, ...) are omitted.

Runs as a Claude Code hook (UserPromptSubmit, PreToolUse/PostToolUse on
AskUserQuestion, Stop). The log file comes from $LEARN_LOG_FILE, set by `learn`.

Claude Code writes the transcript slightly after hooks fire, so instead of
appending, each event re-renders this session's section of the file from the
transcript (idempotent), once now and a few more times shortly after in a
detached process. Anything above this session's section in the file is kept.
"""
import fcntl
import hashlib
import json
import os
import re
import sys
import time

QA_TOOL = "AskUserQuestion"
RETRY_DELAYS = (0.7, 2.0, 5.0, 12.0)


# --- Formatting (same callouts as the original) ---

def callout(kind, title, body_lines):
    lines = [f"> [!{kind}] {title}"]
    for line in body_lines:
        lines.append(">" if line == "" else f"> {line}")
    return "\n".join(lines)


def user_block(text):
    return f"> [!quote] YOU\n\n{text}"


def assistant_block(text):
    return f"> [!abstract] CLAUDE\n\n{text}"


def is_quiz(q):
    return (q.get("header") or "").strip().lower() == "quiz"


def question_callout(q):
    body = (q.get("question") or "").split("\n")
    opts = q.get("options") or []
    if opts:
        body.append("")
        body += [f"{i + 1}. {o.get('label', '')}" for i, o in enumerate(opts)]
    return callout("question", "Quiz" if is_quiz(q) else "Question", body)


def answer_callout(q, answer, note):
    quiz = is_quiz(q)
    if answer is None:
        title = "Quiz — cancelled" if quiz else "Question — cancelled"
        return callout("warning", title, ["(user skipped)"])
    labels = [o.get("label", "") for o in (q.get("options") or [])]
    picked = [a.strip() for a in str(answer).split(", ")] if q.get("multiSelect") else [str(answer).strip()]
    shown = []
    for a in picked:
        shown.append(f"{labels.index(a) + 1}. {a}" if a in labels else (f"Other: {a}" if a else a))
    body = []
    if quiz:
        if picked == ["I don't know"]:
            body.append("Your answer: I don't know")
        else:
            body.append("Your answer: " + (", ".join(shown) or "(none)"))
    else:
        body += shown or ["(no answer)"]
    if note:
        note_lines = str(note).split("\n")
        body += ["", f"Note: {note_lines[0]}"] + note_lines[1:]
    if quiz:
        kind = "question" if picked == ["I don't know"] else "example"
        return callout(kind, "Quiz — your answer", body)
    return callout("example", "Answer", body)


# --- Transcript -> blocks ---

def as_questions(value):
    """AskUserQuestion's `questions`, tolerating a JSON-encoded string."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return [q for q in value or [] if isinstance(q, dict)] if isinstance(value, list) else []


REMINDER_RE = re.compile(r"<system-reminder>[\s\S]*?</system-reminder>")


def clean_user_text(text):
    text = REMINDER_RE.sub("", text or "").strip()
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
    asked = {}  # tool_use_id -> questions
    answered = set()

    def flush():
        if prose:
            blocks.append(assistant_block("\n\n".join(prose)))
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
                    qs = asked[c["tool_use_id"]]
                    answers = parse_answers(e, qs)
                    for q in qs:
                        a, note = answers.get(q.get("question", ""), (None, None))
                        blocks.append(answer_callout(q, a, note))
                    answered.add(c["tool_use_id"])
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
    return "\n\n".join(blocks)


# --- File section management ---

def marker(session_id):
    return f"%% learn md-log · session {session_id} · everything below is rewritten by learn %%"


def write_log(log_file, session_id, body):
    lock_dir = os.path.join(os.environ.get("TMPDIR", "/tmp"), "learn-md-log")
    os.makedirs(lock_dir, exist_ok=True)
    lock_path = os.path.join(lock_dir, hashlib.sha1(os.path.abspath(log_file).encode()).hexdigest()[:16] + ".lock")
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = open(log_file, encoding="utf-8").read() if os.path.exists(log_file) else ""
        mark = marker(session_id)
        if mark in current:
            prefix = current.split(mark, 1)[0].rstrip()
        else:
            prefix = current.rstrip()
        parts = [p for p in (prefix, mark, body) if p]
        new = "\n\n".join(parts) + "\n"
        if new != current:
            tmp = log_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(new)
            os.replace(tmp, log_file)


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
