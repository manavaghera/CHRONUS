# CHRONUS evaluation (2026-10-06T15:33:55)

Corpus: Elon Musk, 16,656 memories. Test set: 51 real question/answer pairs from the TED Gigafactory interview.

## Retrieval: answer-equivalent memories (50 questions)

| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |
|---|---|---|---|---|---|---|
| semantic | 0.16 | 0.32 | 0.14 | 0.24 | 0.42 | 0.34 |
| chronus_pipeline | 0.12 | 0.32 | 0.12 | 0.213 | 0.32 | 0.3 |
| bm25 | 0.1 | 0.2 | 0.08 | 0.159 | 0.24 | 0.6 |

## Retrieval: exact passage only, strict (46 questions)

| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |
|---|---|---|---|---|---|---|
| semantic | 0.087 | 0.152 | 0.051 | 0.122 | 0.217 | 0.304 |
| chronus_pipeline | 0.065 | 0.152 | 0.051 | 0.105 | 0.152 | 0.283 |
| bm25 | 0.043 | 0.109 | 0.036 | 0.085 | 0.152 | 0.587 |

## Retrieval: answer-equivalent, question sentence only (50 questions)

The interviewer's turn without its preamble, closer to what a user types.

| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |
|---|---|---|---|---|---|---|
| semantic | 0.1 | 0.14 | 0.053 | 0.135 | 0.26 | 0.58 |
| chronus_pipeline | 0.1 | 0.16 | 0.053 | 0.127 | 0.16 | 0.54 |
| bm25 | 0.08 | 0.1 | 0.033 | 0.102 | 0.16 | 0.66 |

Paper (Table IV, different corpus): semantic P@1 0.82, BM25 P@1 0.41.

## Match test (TED interview held out)

| Answer | Cosine to real answer | Content-word F1 |
|---|---|---|
| Mix Method (clone) | 0.373 | 0.059 |
| Random memory (baseline) | 0.096 | 0.014 |

## "I don't know" calibration

Best-match distance, answered questions: {'min': 0.245, 'median': 0.41, 'max': 0.609}; unanswerable questions: {'min': 0.48, 'median': 0.638, 'max': 0.73}.

- Current threshold 0.58: answers 98% of answerable, refuses 82% of unanswerable.
- Best balanced threshold 0.58: answers 98%, refuses 82% (chosen and measured on the same questions).
- Held out (chosen on half, measured on the other half, 4 splits; thresholds [0.5, 0.56, 0.58, 0.56]): answers 89%, refuses 86%.
