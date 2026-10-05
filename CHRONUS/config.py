"""
CHRONUS Configuration — Single source of truth for all settings.

All other modules should import from here instead of hardcoding values.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass
class ChronusConfig:
    """CHRONUS system configuration."""

    # === RETRIEVAL ===
    DISTANCE_THRESHOLD: float = 1.1
    """Cosine distance threshold — queries with no memory below this return uncertainty fallback.

    FIX A (Phase 6): was 1.45, which made the fallback unreachable (nearly every
    query matched below it). MiniLM-L6-v2 cosine distances for irrelevant text
    typically run 0.8-1.2, so 1.1 keeps true matches (0.3-1.0) while letting
    irrelevant queries (1.0+) fall through to the uncertainty fallback.
    """

    N_RESULTS: int = 3
    """Number of memories to retrieve per query (paper specifies k=3)."""

    NATURAL_MIN_GROUNDING: float = 0.25
    """Natural-mode answers whose grounding score (share of content words
    found in the evidence + profile) is below this are replaced by the Mix
    Method answer — they are mostly invented. On 2026-10-05 samples, clearly
    invented answers scored 0.14-0.22 and good ones 0.60-1.00; half-invented
    ones (0.27-0.38) slip through, a limit of lexical scoring. 0 disables."""

    MIN_EVIDENCE_WORDS: int = 8
    """Memories shorter than this are skipped when longer ones also pass the
    threshold: short tweets embed close to short questions ("Why Mars?" ->
    "Mars is The New World") but carry almost no content."""

    IMPORTANCE_WEIGHT: float = 0.15
    """Weight for importance score in re-ranking: adjusted = dist - (importance * weight)."""

    # === EMBEDDING ===
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    """Sentence-BERT model for semantic embeddings."""

    EMBEDDING_DIM: int = 384
    """Embedding dimensionality (fixed by model)."""

    BATCH_SIZE: int = 200
    """Batch size for embedding operations."""

    NORMALIZE_EMBEDDINGS: bool = True
    """Whether to L2-normalize embeddings (must match at ingest and query time)."""

    # === CHUNKING ===
    CHUNK_MAX_WORDS: int = 80
    """Maximum words per memory unit chunk."""

    CHUNK_OVERLAP: int = 15
    """Word overlap between adjacent chunks."""

    MIN_CHUNK_CHARS: int = 50
    """Minimum characters for a chunk to be kept."""

    MIN_TWEET_CHARS: int = 10
    """Minimum characters for a tweet to be kept."""

    MAX_TWEET_UNITS: int = 10000
    """Cap on number of tweet memory units (prevents tweet dominance)."""

    # === LLM (Legacy — not used by Mix Method, kept for fallback) ===
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3:8b-instruct-q4_0"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 200
    LLM_CONTEXT_WINDOW: int = 8192

    # === LLM PROVIDER ===
    LLM_PROVIDER: str = "openrouter"  # "ollama" or "openai"-compatible ("openrouter" also accepted)
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    """API key for the OpenAI-compatible provider (also used for OpenRouter).
    Read from the OPENAI_API_KEY env var or CHRONUS/.env (gitignored)."""
    OPENAI_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    """Primary model. ":free" models work on a key with no purchased credits.
    "openrouter/auto" needs credits (HTTP 402 otherwise), and "openrouter/free"
    can route to non-chat models (e.g. a safety classifier), so pin one."""

    OPENAI_FALLBACK_MODELS: list[str] = field(default_factory=lambda: [
        "qwen/qwen3.8-27b:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
    ])
    """OpenRouter tries these in order when the primary errors or is
    rate-limited (free models return 429 under load)."""
    OPENAI_BASE_URL: str = "https://openrouter.ai/api/v1"
    """OpenAI-compatible endpoint. For OpenRouter: https://openrouter.ai/api/v1"""

    # === STORAGE ===
    CHROMA_PATH: str = field(default_factory=lambda: str(Path(__file__).parent / "chroma_db"))
    """Path to ChromaDB persistent storage."""

    COLLECTION_NAME: str = "elon_musk"
    """Default ChromaDB collection name."""

    MODELS_DIR: str = field(default_factory=lambda: str(Path(__file__).parent / "models"))
    """Directory containing persona model files."""

    DATA_DIR: str = field(default_factory=lambda: str(Path(__file__).parent / "data"))
    """Directory containing interview protocol and other data."""

    # === SERVER ===
    HOST: str = "127.0.0.1"
    """Server bind address (localhost only — no auth on endpoints)."""

    PORT: int = 8001
    """Server port."""

    # === VOICE (Optional) ===
    VOICE_ENGINE: str = "xtts"
    """Voice synthesis engine: 'xtts' (local) or 'elevenlabs' (cloud)."""

    SPEAKER_WAV_PATH: str = field(default_factory=lambda: str(
        Path(__file__).parent / "07-Voice" / "reference_elon.wav"
    ))
    """Path to reference speaker audio for voice cloning."""

    ELEVENLABS_API_KEY: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    """API key for ElevenLabs cloud TTS (set via ELEVENLABS_API_KEY env var)."""

    # === PERSONA DEFAULTS ===
    DEFAULT_PERSONA: str = "elon_musk"
    """Default persona to load."""

    IDENTITY_CARD_PATH: str = field(default_factory=lambda: str(
        Path(__file__).parent / "models" / "elon_musk" / "identity_card.json"
    ))
    """Path to default persona's identity card."""

    SIGNATURE_PHRASES_PATH: str = field(default_factory=lambda: str(
        Path(__file__).parent / "models" / "elon_musk" / "signature_phrases.txt"
    ))
    """Path to default persona's signature phrases."""


def _load_env_file(path: os.PathLike) -> None:
    """Minimal dependency-free .env loader (no python-dotenv required).

    Loads KEY=VALUE lines into the environment WITHOUT overriding existing
    environment variables. Used so the OpenRouter/ElevenLabs API keys can live
    in CHRONUS/.env (gitignored) instead of committed code.
    """
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Load CHRONUS/.env (next to this file) BEFORE constructing the singleton so
# field default_factories that read env vars pick up the values.
_load_env_file(Path(__file__).parent / ".env")


# Singleton instance
config = ChronusConfig()

if __name__ == "__main__":
    print("CHRONUS Configuration")
    print("=" * 50)
    for field_name, field_value in vars(config).items():
        if not field_name.startswith("_"):
            print(f"  {field_name}: {field_value}")
