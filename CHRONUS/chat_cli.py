"""CHRONUS CLI - Elon Musk Chat via command line argument or interactive loop"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.getcwd(), "06-Testing"))

from chat_elon import chat, identity_card_text, collection, model
from elon_few_shot import few_shot_block
from post_process import scrub
import chromadb, requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b-instruct-q4_0"

if len(sys.argv) > 1:
    # Single query mode
    query = " ".join(sys.argv[1:])
    chat(query)
else:
    # Interactive mode with flush
    print("\n" + "=" * 60)
    print("CHRONUS - Elon Musk Chat (type 'quit' to exit)")
    print("=" * 60)
    print()
    while True:
        try:
            query = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not query or query.lower() in ("quit", "exit", "q"):
            break
        chat(query)
        print()
