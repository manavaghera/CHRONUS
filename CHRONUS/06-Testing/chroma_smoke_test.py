#!/usr/bin/env python3
"""Quick ChromaDB smoke test for the Elon Musk collection."""

import chromadb


def main() -> None:
    client = chromadb.PersistentClient(path="chroma_db")
    col = client.get_collection("elon_musk")

    print(f"Count: {col.count():,}")
    print()

    questions = [
        "What does Elon think about Mars colonization?",
        "Why is Elon worried about AI?",
        "What did Elon say about working hard?",
        "What does Elon think about free speech?",
        "Why does Elon believe we are in a simulation?",
    ]

    for question in questions:
        print("=" * 70)
        print(f"Q: {question}")
        print("=" * 70)
        results = col.query(query_texts=[question], n_results=5)
        for i, (doc, meta, dist) in enumerate(
            zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ),
            start=1,
        ):
            print(
                f"[{i}] d={dist:.3f}  "
                f"{meta['source_file'][:45]:45s}  "
                f"type={meta['source_type']:10s}  "
                f"imp={meta['importance_score']}"
            )
            print(f"    {doc[:160]}...")
        print()


if __name__ == "__main__":
    main()
