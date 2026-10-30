#!/usr/bin/env python3
"""quiz — grade a quiz the moment the learner answers it.

Claude Code port of the grading half of extensions/quiz.ts from
amosblomqvist/learn. The teacher asks graded questions with AskUserQuestion,
using one of the graded headers below, and puts the answer key in the call's
hidden `metadata.source`:

    {"correct": ["<option label>", ...], "explanation": "<why>"}

As a PostToolUse hook on AskUserQuestion this grades the learner's pick
(exact-set match; "I don't know" is its own signal, never ✗), shows the
feedback in the terminal, and hands the grade back to the teacher.
"""
import json
import sys

DONT_KNOW = "I don't know"
# Graded headers -> how they're labelled in the note.
GRADED = {"probe": "Pre-quiz", "quiz": "Quiz", "review": "Topic quiz", "final": "Final quiz"}


def kind(q):
    return (q.get("header") or "").strip().lower()


def is_quiz(q):
    return kind(q) in GRADED


def label(q):
    return GRADED.get(kind(q), "Question")


def answer_key(tool_input):
    """The {"correct": [...], "explanation": str} key from metadata.source, or None."""
    source = ((tool_input or {}).get("metadata") or {}).get("source")
    if not source:
        return None
    try:
        key = json.loads(source) if isinstance(source, str) else source
    except json.JSONDecodeError:
        return None
    if not isinstance(key, dict) or "correct" not in key:
        return None
    correct = key["correct"]
    key["correct"] = [correct] if isinstance(correct, str) else [str(c) for c in correct or []]
    key["explanation"] = str(key.get("explanation") or "")
    return key


def grade(q, answer, key):
    """Grade one quiz answer. Returns a dict, or None if it can't be graded."""
    if key is None or answer is None:
        return None
    labels = [o.get("label", "") for o in (q.get("options") or [])]
    picked = [a.strip() for a in str(answer).split(", ")] if q.get("multiSelect") else [str(answer).strip()]
    correct = [c.strip() for c in key["correct"]]
    correct_idx = [labels.index(c) + 1 for c in correct if c in labels]
    result = {
        "picked": picked,
        "picked_idx": [labels.index(p) + 1 if p in labels else None for p in picked],
        "correct": correct,
        "correct_idx": correct_idx,
        "explanation": key["explanation"],
        "dont_know": picked == [DONT_KNOW],
        "other": any(p not in labels for p in picked),
    }
    result["is_correct"] = (not result["dont_know"] and not result["other"]
                            and sorted(picked) == sorted(correct))
    return result


def fmt_options(idx, labels):
    return ", ".join(f"{i}. {l}" if i else f"Other: {l}" for i, l in zip(idx, labels))


def feedback(g):
    if g["dont_know"]:
        head = "? I don't know"
    elif g["other"]:
        head = "✎ Your own answer — the teacher will grade it"
    elif g["is_correct"]:
        head = "✓ Correct"
    else:
        head = "✗ Incorrect"
    lines = [head]
    if not g["dont_know"]:
        lines.append("Your answer: " + fmt_options(g["picked_idx"], g["picked"]))
    lines.append("Correct answer: " + fmt_options(g["correct_idx"], g["correct"]))
    if g["explanation"]:
        lines += ["", g["explanation"]]
    return "\n".join(lines)


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if data.get("tool_name") != "AskUserQuestion":
        return
    tool_input = data.get("tool_input") or {}
    response = data.get("tool_response") or {}
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            response = {}
    answers = response.get("answers") or {} if isinstance(response, dict) else {}
    quizzes = [q for q in tool_input.get("questions") or [] if isinstance(q, dict) and is_quiz(q)]
    if not quizzes:
        return
    key = answer_key(tool_input)
    shown, context = [], []
    for q in quizzes:
        g = grade(q, answers.get(q.get("question", "")), key)
        if g is None:
            context.append("Quiz not auto-graded (no answer key in metadata.source, or no answer). "
                           "Start your reply with the feedback line and the explanation yourself.")
            continue
        shown.append(feedback(g))
        if g["dont_know"]:
            verdict = "dontKnow — the learner honestly did not know (a gap to teach into, not a wrong answer)"
        elif g["other"]:
            verdict = "typed their own answer — grade it on its meaning and start your reply with ✓ or ✗ and why"
        else:
            verdict = "correct" if g["is_correct"] else "incorrect"
        nxt = ("Continue from this result: while probing, adapt your next question; while teaching, write the "
               "next node's lesson text before any further quiz."
               if g["is_correct"] else
               "Continue from this result: while probing, adapt your next question; while teaching, this node "
               "isn't solid yet, so re-teach it in prose from a different angle before checking it again.")
        context.append(f"Quiz graded: {verdict}. The learner has already been shown ✓/✗, the correct answer "
                       f"and your explanation, so don't repeat them. {nxt}")
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(context)}}
    if shown:
        out["systemMessage"] = "\n\n".join(shown)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
