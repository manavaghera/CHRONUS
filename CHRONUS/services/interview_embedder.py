"""
CHRONUS Interview Embedder — Embeds structured interview responses into ChromaDB.

Usage:
    # Embed a single response
    embed_single_response("Q1", "I'm an engineer at heart...", collection, embedder)

    # Embed all responses from a JSON file
    embed_from_file("models/elon_musk/interview_responses.json", collection, embedder)
"""

import json
import hashlib
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.interview_protocol import (
    get_question_by_id,
    get_all_questions,
    format_qa_for_embedding,
    build_interview_metadata,
    INTERVIEW_QUESTIONS
)


def generate_memory_id(text: str) -> str:
    """Generate a stable MD5-based memory ID from text content."""
    return "int_" + hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


def embed_single_response(
    question_id: str,
    answer: str,
    collection,
    embedder,
    person: str = "elon_musk",
    origin: str = "self",
) -> dict:
    """Embed a single interview Q&A pair into ChromaDB.

    Args:
        question_id: Question ID (e.g., "Q7")
        answer: The answer text
        collection: ChromaDB collection object
        embedder: SentenceTransformer model
        person: Person identifier
        origin: Who answered — "self" (the person), "family", "friend",
            "colleague", or "synthesized" (generated stand-in). Drives how the
            answer is attributed (services/provenance.py).

    Returns:
        dict with embedding result info
    """
    question = get_question_by_id(question_id)
    if not question:
        return {"success": False, "error": f"Unknown question ID: {question_id}"}

    # Find which dimension this question belongs to
    dimension = None
    for dim_id, dim_data in INTERVIEW_QUESTIONS.items():
        for q in dim_data["questions"]:
            if q["id"] == question_id:
                dimension = dim_id
                break
        if dimension:
            break

    # Format for embedding
    formatted_text = format_qa_for_embedding(question, answer)

    # Generate stable ID
    memory_id = generate_memory_id(formatted_text)

    # Build metadata
    metadata = build_interview_metadata(question, dimension)
    metadata["memory_id"] = memory_id
    metadata["person"] = person
    metadata["origin"] = origin

    # Generate embedding
    embedding = embedder.encode([formatted_text], normalize_embeddings=True).tolist()[0]

    # Upsert to ChromaDB
    collection.upsert(
        ids=[memory_id],
        documents=[formatted_text],
        embeddings=[embedding],
        metadatas=[metadata]
    )

    return {
        "success": True,
        "question_id": question_id,
        "dimension": dimension,
        "memory_id": memory_id,
        "text_length": len(formatted_text)
    }


def embed_from_file(
    filepath: str,
    collection,
    embedder,
    person: str = "elon_musk"
) -> dict:
    """Embed all interview responses from a JSON file.

    Expected JSON format:
    [
        {
            "question_id": "Q1",
            "question": "How would you describe...",
            "answer": "I'm an engineer at heart...",
            "source": "synthesized_from_interviews",
            "dimension": "personality"
        },
        ...
    ]

    Args:
        filepath: Path to JSON file
        collection: ChromaDB collection
        embedder: SentenceTransformer model
        person: Person identifier

    Returns:
        Summary dict with success/failure counts
    """
    path = Path(filepath)
    if not path.exists():
        return {"success": False, "error": f"File not found: {filepath}"}

    with open(path, "r", encoding="utf-8") as f:
        responses = json.load(f)

    if not isinstance(responses, list):
        return {"success": False, "error": "JSON must be a list of response objects"}

    results = {"success": True, "embedded": 0, "failed": 0, "errors": []}

    for resp in responses:
        question_id = resp.get("question_id")
        answer = resp.get("answer", "")

        if not question_id or not answer:
            results["failed"] += 1
            results["errors"].append(f"Missing question_id or answer: {resp}")
            continue

        result = embed_single_response(
            question_id, answer, collection, embedder, person, origin=resp.get("origin", "self"),
        )
        if result["success"]:
            results["embedded"] += 1
            print(f"  [OK] {question_id} ({result['dimension']}) - {len(answer)} chars")
        else:
            results["failed"] += 1
            results["errors"].append(result["error"])

    print(f"\nInterview embedding complete: {results['embedded']} embedded, {results['failed']} failed")
    return results


if __name__ == "__main__":
    # Demo usage (requires ChromaDB and embedder to be available)
    print("CHRONUS Interview Embedder")
    print("Run via: python -c 'from services.interview_embedder import embed_from_file; ...'")
    print("\nQuestions available:")
    for q in get_all_questions():
        print(f"  {q['id']}: {q['question'][:60]}...")
