"""Data pipeline guarantees (merge_sources.py output and the live collection)."""

import json

import pytest

import merge_sources
from evaluation.ted_qa import load_pairs


@pytest.fixture(scope="module")
def units():
    with merge_sources.MEMORY_JSONL.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_superseded_files_still_exist():
    missing = [p for p in merge_sources.SUPERSEDED_FILES if not (merge_sources.CLEANED_DIR / p).exists()]
    assert not missing, f"renamed? the skip list no longer matches: {missing}"


def test_no_raw_duplicates_or_retweets(units):
    assert not any(u["source_file"].endswith(".txt") for u in units)
    assert not any(u["text"].startswith("RT @") for u in units)


def test_memory_ids_unique(units):
    assert len({u["memory_id"] for u in units}) == len(units)


def test_ted_talks_are_interviews(units):
    assert {u["source_type"] for u in units if u["source_file"].upper().startswith("TED")} == {"interview"}


@pytest.mark.corpus
def test_collection_matches_pipeline_output(srv, units):
    interview = srv.collection.get(where={"source_type": "interview_protocol"}, include=["metadatas"])["metadatas"]
    assert srv.collection.count() == len(units) + len(interview)
    assert len(interview) == 25 and {m["origin"] for m in interview} == {"synthesized"}


def test_evaluation_pairs_extract():
    pairs = load_pairs()
    assert len(pairs) >= 45 and all(p["question"] and len(p["answer"].split()) >= 25 for p in pairs)
