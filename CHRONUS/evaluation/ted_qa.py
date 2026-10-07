"""
Real question/answer pairs for evaluation, from the one transcript with
speaker labels: the TED Gigafactory interview (Chris Anderson asks, Elon Musk
answers). Each pair is (interviewer question, Elon's actual answer).

Elon's answers are also in the memory store (rebuild_elon.py keeps only his
turns of this interview, "TED Tesla fract.txt"), so the pairs serve two tests:
* retrieval — can the system find the memory holding his real answer?
* match test — with that interview held out, how close is the clone's answer
  to what he really said?
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_TRANSCRIPT = ROOT / "01-Raw-Data" / "Interviews" / "TED Tesla fract.txt"
# This interview inside the memory store (source_file of its memories)
SOURCE_IN_MEMORY = "TED Tesla fract.txt"

_SPEAKER = re.compile(r"\b(Chris Anderson|CA|Elon Musk|EM):\s")
_TIMESTAMP = re.compile(r"\b\d{2}:\d{2}:\d{2}\.\d{1,3}\b")
MIN_QUESTION_WORDS = 6
MIN_ANSWER_WORDS = 25


def _clean(text: str) -> str:
    text = _TIMESTAMP.sub(" ", text)
    text = re.sub(r"(?<=[a-z,.])(?=[A-Z][a-z])", " ", text)  # "greatto see" style joins
    return re.sub(r"\s+", " ", text).strip()


def question_only(turn: str) -> str:
    """The question itself, without the interviewer's preamble: the last
    sentence that asks something (else the last sentence). Closer to what a
    user types into the chat."""
    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", turn) if s.strip()]
    asking = [s for s in sentences if s.endswith("?")]
    return (asking or sentences or [turn])[-1]


def load_pairs(path: Path = RAW_TRANSCRIPT) -> list[dict]:
    """Return [{"id", "question", "answer"}] for every interviewer turn
    followed by an Elon answer long enough to judge."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = raw.split("\n", 3)[-1] if raw.startswith("#") else raw  # drop the tactiq header
    parts = _SPEAKER.split(raw)
    # parts = [preamble, speaker, text, speaker, text, ...]
    turns = []
    for speaker, text in zip(parts[1::2], parts[2::2]):
        who = "elon" if speaker in ("Elon Musk", "EM") else "host"
        text = _clean(text)
        if turns and turns[-1][0] == who:  # merge consecutive turns by one speaker
            turns[-1] = (who, f"{turns[-1][1]} {text}")
        else:
            turns.append((who, text))

    pairs = []
    for (who_q, question), (who_a, answer) in zip(turns, turns[1:]):
        if who_q == "host" and who_a == "elon" \
                and len(question.split()) >= MIN_QUESTION_WORDS and len(answer.split()) >= MIN_ANSWER_WORDS:
            pairs.append({"id": f"ted{len(pairs) + 1:02d}", "question": question, "answer": answer})
    return pairs


if __name__ == "__main__":
    pairs = load_pairs()
    print(f"{len(pairs)} question/answer pairs")
    for p in pairs[:5]:
        print(f"\n[{p['id']}] Q: {p['question'][:160]}\n      A: {p['answer'][:160]}")
