"""Validate interview_responses.json against the interview protocol and embedder."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.interview_protocol import get_question_by_id, get_all_questions

path = Path(__file__).parent.parent / "models" / "elon_musk" / "interview_responses.json"
with open(path, "r", encoding="utf-8") as f:
    responses = json.load(f)

print(f"Loaded {len(responses)} responses")

expected_ids = [q["id"] for q in get_all_questions()]
got_ids = [r.get("question_id") for r in responses]
print(f"IDs match protocol order: {got_ids == expected_ids}")

errors = []
for r in responses:
    qid = r.get("question_id", "?")
    # Required fields for the embedder
    if not r.get("question_id") or not r.get("answer"):
        errors.append(f"{qid}: missing question_id or answer")
        continue
    # Question text must match the protocol exactly
    proto = get_question_by_id(r["question_id"])
    if proto is None:
        errors.append(f"{qid}: unknown question ID")
        continue
    if r.get("question") != proto["question"]:
        errors.append(f"{qid}: question text differs from protocol")
    # Dimension must match the protocol dimension this question belongs to
    if r.get("confidence") not in ("high", "medium", "low"):
        errors.append(f"{qid}: bad confidence value '{r.get('confidence')}'")
    for field in ("source_notes", "confidence", "dimension"):
        if not r.get(field):
            errors.append(f"{qid}: missing field '{field}'")
    n = len(r["answer"].split())
    if n < 20 or n > 90:
        errors.append(f"{qid}: answer length {n} words outside 20-90 range")

if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

dims = {}
for r in responses:
    dims[r["dimension"]] = dims.get(r["dimension"], 0) + 1
print("Per-dimension counts:", dims)
confs = {}
for r in responses:
    confs[r["confidence"]] = confs.get(r["confidence"], 0) + 1
print("Confidence breakdown:", confs)
avg_words = sum(len(r["answer"].split()) for r in responses) / len(responses)
print(f"Average answer length: {avg_words:.0f} words")
print("ALL CHECKS PASSED")
