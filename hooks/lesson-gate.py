#!/usr/bin/env python3
"""lesson-gate — make sure the lesson is written down before it's quizzed.

Sonnet thinks before it answers, and sometimes it works out a node's
explanation (or the whole plan) in that hidden thinking and goes straight to
the quiz. The learner then never sees the teaching, and the Obsidian note,
which mirrors only visible text, gets a quiz with no lesson above it.

As a PreToolUse hook on AskUserQuestion this checks two things, and blocks the
question (telling the teacher exactly what to fix) when either fails:

  1. every graded question (Probe / Quiz / Review / Final) carries its answer
     key in metadata.source, so quiz.py can grade it — Sonnet sometimes drops it;
  2. node quiz-checks ("Quiz") and plan approvals ("Plan") come after lesson
     text the learner can actually see, written since their last answer.

Fails open if the transcript can't be read in time, or after three blocks in a row.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from quiz import GRADED, answer_key  # noqa: E402

GATED = {"quiz": 250, "plan": 250}  # header -> minimum visible characters since the last answer
MAX_STRIKES = 3
FLUSH_WAIT = 4.0
STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ".state")
KEY_EXAMPLE = ('"metadata": {"source": "{\\"correct\\": [\\"<exact label of the correct option>\\"], '
               '\\"explanation\\": \\"<why it is correct>\\"}"}')


def entries(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return out


def text_before(transcript, tool_use_id):
    """Visible teacher text between the learner's last turn/answer and this tool call, or None if not flushed yet."""
    since = 0
    for e in transcript:
        msg = e.get("message") if isinstance(e.get("message"), dict) else None
        if not msg or e.get("isSidechain") or e.get("type") not in ("user", "assistant"):
            continue
        content = msg.get("content")
        if e["type"] == "user":
            if isinstance(content, str):
                if content.strip() and not content.lstrip().startswith("<"):
                    since = 0
                continue
            for c in content or []:
                if not isinstance(c, dict):
                    continue
                # A real answer resets the count; a blocked/failed call does not.
                if c.get("type") == "tool_result" and not c.get("is_error"):
                    since = 0
                elif c.get("type") == "text" and c.get("text", "").strip() and not c["text"].lstrip().startswith("<"):
                    since = 0
            continue
        for c in content or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                since += len(c.get("text", "").strip())
            elif c.get("type") == "tool_use" and c.get("id") == tool_use_id:
                return since
    return None


def strikes(session_id, update=None):
    path = os.path.join(STATE_DIR, f"gate-{session_id}.json")
    try:
        n = json.load(open(path)).get("strikes", 0)
    except (OSError, json.JSONDecodeError):
        n = 0
    if update is not None:
        os.makedirs(STATE_DIR, exist_ok=True)
        if update:
            json.dump({"strikes": update}, open(path, "w"))
        elif os.path.exists(path):
            os.remove(path)
    return n


def deny(session, reason):
    strikes(session, strikes(session) + 1)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def key_problem(tool_input, questions):
    """Why a graded question can't be auto-graded, or None if its answer key is fine."""
    graded = [q for q in questions if (q.get("header") or "").strip().lower() in GRADED]
    if not graded:
        return None
    key = answer_key(tool_input)
    if key is None or not key["correct"]:
        return "it has no answer key"
    if not key["explanation"].strip():
        return "its answer key has no explanation"
    labels = {o.get("label", "") for q in graded for o in q.get("options") or []}
    missing = [c for c in key["correct"] if c not in labels]
    if missing:
        return f"its answer key names {missing[0]!r}, which is not one of the option labels"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    tool_input = data.get("tool_input") or {}
    questions = tool_input.get("questions")
    if isinstance(questions, str):
        try:
            questions = json.loads(questions)
        except json.JSONDecodeError:
            return
    questions = [q for q in questions or [] if isinstance(q, dict)]
    session = data.get("session_id", "x")
    if strikes(session) >= MAX_STRIKES:
        strikes(session, 0)
        return

    problem = key_problem(tool_input, questions)
    if problem:
        return deny(session, f"Blocked: this graded question can't be graded because {problem}. Add the hidden "
                             f"answer key and ask again, otherwise unchanged: {KEY_EXAMPLE}")

    headers = [(q.get("header") or "").strip().lower() for q in questions]
    need = max((GATED[h] for h in headers if h in GATED), default=0)
    if not need:
        strikes(session, 0)
        return
    since, deadline = None, time.time() + FLUSH_WAIT
    while since is None and time.time() < deadline:
        since = text_before(entries(data.get("transcript_path")), data.get("tool_use_id"))
        if since is None:
            time.sleep(0.25)
    if since is None or since >= need:
        strikes(session, 0)
        return
    what = ("the plan (approach + dependency map)" if "plan" in headers
            else "this node's lesson (motivate → establish → connect, or the re-teach)")
    deny(session, f"Blocked: since the learner's last answer you have written only {since} characters of "
                  f"visible text, so they have not seen {what}. They read only your visible message (that is "
                  "what goes into their Obsidian note); what you worked out in your thinking, or only meant to "
                  f"write, is invisible to them. Write {what} out in full as your message now, then ask this "
                  "question again.")


if __name__ == "__main__":
    main()
