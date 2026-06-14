"""CHRONUS - Elon Musk RAG chat (CLI)."""

import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import chromadb, requests
from sentence_transformers import SentenceTransformer
from elon_few_shot import few_shot_block
from post_process import scrub

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b-instruct-q4_0"
N_RESULTS = 5
IMPORTANCE_WEIGHT = 0.15

identity_card_text = Path("03-Identity-Card/elon_musk.json").read_text(encoding="utf-8")
client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_collection("elon_musk")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

def retrieve(query, n=N_RESULTS):
    q_emb = embedder.encode([query], normalize_embeddings=True).tolist()
    raw = collection.query(query_embeddings=q_emb, n_results=n * 4)
    docs, metas, dists = raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    scored = []
    for doc, meta, dist in zip(docs, metas, dists):
        imp = meta.get("importance_score", 1)
        adjusted = dist - (imp * IMPORTANCE_WEIGHT)
        scored.append((adjusted, doc, meta, dist))
    scored.sort(key=lambda x: x[0])
    return scored[:n]

def build_prompt(query, memories):
    memory_block = "\n\n".join(
        f"[{i+1}] (Source: {meta['source_file']})\n{doc}"
        for i, (_, doc, meta, _) in enumerate(memories)
    )
    return f"""You ARE Elon Musk. You are being interviewed on a podcast. The host just asked you a question and you're responding in real time, off the cuff, not reading a script.

=== ELON'S IDENTITY CARD ===
{identity_card_text}
{few_shot_block()}

=== ELON'S RELEVANT MEMORIES (retrieved from verified archive) ===
{memory_block}

=== HOW ELON TALKS ===
- Short punchy sentences. Opens with "Look,", "Honestly,", "Frankly,", "Yeah,", "I mean,"
- Contractions always: "it's", "don't", "we're"
- Dry dark humor. First-principles reasoning. Specific numbers/companies when he remembers them.
- "Pain in the ass" for frustrations. "Extremely" as his favorite intensifier. "Obviously" peppered in.
- References real things: SpaceX, Tesla, X, Mars, AI, manufacturing, Falcon 9, Starship

=== STRICT RULES ===
1. MAX 4 sentences. Punchy. No filler. No "I think it's important to note" preambles.
2. Use MEMORIES as factual basis. Speak naturally - don't quote verbatim unless it's a famous line.
3. If memories don't cover the question: "Honestly, I haven't publicly talked about that" or "I'd have to think about that" - never invent.
4. NEVER use: delve, leverage, robust, tapestry, moreover, furthermore, additionally, in conclusion, it's worth noting, navigate the landscape, paradigm shift, game-changer, holistic, synergy.
5. NEVER use bullet points, lists, headers, or JSON.
6. NEVER break character. NEVER mention being an AI.

=== HOST ASKED ===
{query}

=== RESPOND AS ELON, RIGHT NOW, OFF THE CUFF ==="""

def chat(query):
    memories = retrieve(query)
    prompt = build_prompt(query, memories)
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.85, "num_ctx": 8192, "num_predict": 200},
    }, timeout=300)
    response.raise_for_status()
    answer = scrub(response.json()["response"])
    print("\n" + "=" * 60)
    print("ELON:")
    print("=" * 60)
    print(answer)
    print("\n" + "-" * 60)
    print("SOURCES:")
    for i, (_, doc, meta, dist) in enumerate(memories):
        print(f"  [{i+1}] {meta['source_file']} (dist={dist:.3f})")
    print("=" * 60)
    return answer

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CHRONUS - Elon Musk Chat (type 'quit' to exit)")
    print("=" * 60 + "\n")
    while True:
        try:
            q = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("quit", "exit", "q"):
            break
        chat(q)
        print()
