"""Data pipeline guarantees (merge_sources.py output and the live collection)."""

import json

import pytest

import merge_sources
from evaluation.ted_qa import load_pairs


@pytest.fixture(scope="module")
def units():
    if not merge_sources.MEMORY_JSONL.exists():
        # not in the repository (it quotes a copyrighted biography): python rebuild_elon.py makes it
        pytest.skip("memory units not built here (python rebuild_elon.py)")
    with merge_sources.MEMORY_JSONL.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_superseded_files_still_exist():
    # Books/ (copyrighted biography excerpts) is kept locally, not in the repo
    local_only = ("Books/",)
    missing = [p for p in merge_sources.SUPERSEDED_FILES
               if not (merge_sources.CLEANED_DIR / p).exists()
               and not (p.startswith(local_only) and not (merge_sources.CLEANED_DIR / "Books").exists())]
    assert not missing, f"renamed? the skip list no longer matches: {missing}"


def test_no_raw_duplicates_or_retweets(units):
    # rebuild_elon.py reads the raw transcripts; their hand-cleaned copies (which lost every "like") are gone
    assert not any(u["source_file"].endswith(("clean.md", "CLEAN.md", "fractory.md")) for u in units)
    assert not any(u["text"].startswith("RT @") for u in units)


def test_rebuilt_units_keep_their_words_dates_and_sentences(units):
    import re

    transcripts = [u for u in units if u["source_type"] == "interview"]
    assert transcripts and all(u.get("date") and isinstance(u.get("start_seconds"), int) for u in transcripts)
    # four interviews (raw captions, no punctuation) used to be one 10,000+ word memory each
    assert max(len(u["text"].split()) for u in transcripts) < 300
    punctuated = [u for u in transcripts if u.get("punctuated", True)]
    ended = sum(bool(re.search(r"[.!?][\"'”’)]*$", u["text"])) for u in punctuated)
    assert ended / len(punctuated) > 0.95  # 44% used to end mid-sentence
    assert any(" like " in u["text"] for u in transcripts)  # real "like"s are kept
    biography = [u for u in units if u["source_type"] == "pdf"]
    assert not any("\x00" in u["text"] or re.search(r"\b(?:rst|nancial|dierent)\b", u["text"]) for u in biography)
    non_tweets = [u for u in units if u["source_type"] != "tweet"]
    assert sum(bool(u.get("date")) for u in non_tweets) / len(non_tweets) > 0.9  # 97% used to be "unknown"
    # TED and Don Lemon name their speakers: only Elon's turns are kept
    labelled = [u for u in transcripts if u["source_file"] in ("TED Tesla fract.txt", "Don Lemon.txt")]
    assert labelled and all(u["speaker_verified"] for u in labelled)
    assert not any(u["text"].startswith(("CA:", "Chris Anderson:")) for u in labelled)


def test_memory_ids_unique(units):
    assert len({u["memory_id"] for u in units}) == len(units)


def test_ted_talks_are_interviews(units):
    assert {u["source_type"] for u in units if u["source_file"].upper().startswith("TED")} == {"interview"}


@pytest.mark.corpus
def test_collection_matches_pipeline_output(srv, units):
    interview = srv.collection.get(where={"source_type": "interview_protocol"}, include=["metadatas"])["metadatas"]
    assert srv.collection.count() == len(units) + len(interview)
    assert len(interview) == 25 and {m["origin"] for m in interview} == {"synthesized"}


def _captions(tmp_path, lines, name="talk.txt"):
    """A transcript in the raw tactiq format: '00:01:02.000 text' per caption line."""
    body = "".join(f"00:{s // 60:02d}:{s % 60:02d}.000 {text}\n" for s, text in lines)
    path = tmp_path / name
    path.write_text(f"# tactiq.io free youtube transcript\n# A talk\n# https://www.youtube.com/watch/abcdefghijk\n\n{body}", encoding="utf-8")
    return path


def test_unpunctuated_captions_are_cut_between_lines(tmp_path):
    import elon_sources as es

    # 400 words of raw auto-captions, no punctuation, one long pause after line 10
    lines, at = [], 0
    for i in range(80):
        lines.append((at, f"word{i}a word{i}b word{i}c word{i}d word{i}e"))
        at += 9 if i == 9 else 2
    sentences, labelled = es.read_transcript(_captions(tmp_path, lines))
    assert not labelled and len(sentences) > 4 and not any(s["punctuated"] for s in sentences)
    # used to be one 400-word "sentence"; now pieces, the first ending at the pause
    assert len(sentences[0]["text"].split()) == 50
    assert all(len(s["text"].split()) <= es.CAPTION_MAX_WORDS for s in sentences)
    assert " ".join(s["text"] for s in sentences) == " ".join(text for _, text in lines)  # every word kept
    assert [s["start"] for s in sentences] == sorted(s["start"] for s in sentences)


def test_punctuated_transcripts_still_end_at_sentences(tmp_path):
    import elon_sources as es

    lines = [(i * 2, "We want to make life multiplanetary. It is the next step") for i in range(40)]
    sentences, _ = es.read_transcript(_captions(tmp_path, lines))
    assert all(s["punctuated"] for s in sentences)
    assert all(s["text"].endswith(".") for s in sentences[:-1])


def test_inferred_speakers_keep_only_elons_lines(tmp_path, monkeypatch):
    import elon_sources as es
    import rebuild_elon
    import speaker_labels

    lines = [(0, "Welcome to the show. Thanks for coming."), (4, "Thanks for having me. Mars is the goal."),
             (8, "Why Mars? Tell us."), (12, "Because a multiplanetary species is safer. That is the reason.")]
    path = _captions(tmp_path, lines)
    monkeypatch.setattr(es, "RAW_INTERVIEWS", tmp_path)
    sentences, _ = es.read_transcript(path)
    who = {"Welcome to the show.": "O", "Thanks for coming.": "O", "Why Mars?": "O", "Tell us.": "O"}
    labels = [who.get(s["text"], "E") for s in sentences]
    monkeypatch.setattr(speaker_labels, "trusted_labels", lambda name, s: labels)
    units = rebuild_elon.transcript_units({path.name: {"title": "A talk", "url": "https://www.youtube.com/watch?v=abcdefghijk"}})
    text = " ".join(u["text"] for u in units)
    assert "Mars is the goal." in text and "multiplanetary species" in text
    assert "Welcome" not in text and "Why Mars?" not in text
    assert all(u["speaker_inferred"] and u["speaker_verified"] is False for u in units)

    # without (enough) labels nothing is dropped, and nothing claims to be inferred
    monkeypatch.setattr(speaker_labels, "trusted_labels", lambda name, s: None)
    units = rebuild_elon.transcript_units({path.name: {"title": "A talk", "url": None}})
    assert "Welcome" in " ".join(u["text"] for u in units) and not any(u.get("speaker_inferred") for u in units)


def test_only_validated_speaker_labels_are_used(tmp_path, monkeypatch):
    import json

    import speaker_labels as sl

    monkeypatch.setattr(sl, "LABELS_PATH", tmp_path / "labels.json")
    sentences = [{"text": "Why Mars?"}, {"text": "Because we should be multiplanetary."}]
    entry = {"fingerprint": sl.fingerprint(sentences), "model": "small-model", "labels": "OE"}
    sl.LABELS_PATH.write_text(json.dumps({"talk.txt": entry}), encoding="utf-8")
    assert sl.labels_for("talk.txt", sentences) == ["O", "E"]
    assert sl.trusted_labels("talk.txt", sentences) is None  # never validated

    passed = {"kept_that_are_elon": 0.95, "accuracy": 0.9}
    weak = {"kept_that_are_elon": 0.707, "accuracy": 0.648}  # what llama3 8B scored on TED
    for report, expected in ((dict.fromkeys(sl.LABELLED, passed), ["O", "E"]),
                             ({sl.LABELLED[0]: passed, sl.LABELLED[1]: weak}, None)):
        sl.LABELS_PATH.write_text(json.dumps({"talk.txt": entry, "validation:small-model": report}), encoding="utf-8")
        assert sl.trusted_labels("talk.txt", sentences) == expected
    assert sl.trusted_labels("talk.txt", sentences[:1]) is None  # the transcript changed since it was labelled


def test_evaluation_pairs_extract():
    pairs = load_pairs()
    assert len(pairs) >= 45 and all(p["question"] and len(p["answer"].split()) >= 25 for p in pairs)
