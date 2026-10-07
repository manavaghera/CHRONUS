# CHRONUS evaluation (2026-10-07T20:13:01)

Corpus: Elon Musk, 16,731 memories. Test set: 51 real question/answer pairs from the TED Gigafactory interview.

## Retrieval: answer-equivalent memories (51 questions)

| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |
|---|---|---|---|---|---|---|
| semantic | 0.176 | 0.235 | 0.118 | 0.217 | 0.333 | 0.353 |
| chronus_pipeline | 0.196 | 0.216 | 0.124 | 0.203 | 0.216 | 0.333 |
| pipeline_no_importance | 0.176 | 0.235 | 0.124 | 0.199 | 0.235 | 0.373 |
| hybrid | 0.157 | 0.275 | 0.131 | 0.209 | 0.275 | 0.373 |
| bm25 | 0.078 | 0.176 | 0.059 | 0.139 | 0.255 | 0.647 |

## Retrieval: exact passage only, strict (51 questions)

| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |
|---|---|---|---|---|---|---|
| semantic | 0.078 | 0.137 | 0.046 | 0.134 | 0.333 | 0.353 |
| chronus_pipeline | 0.078 | 0.137 | 0.059 | 0.105 | 0.137 | 0.333 |
| pipeline_no_importance | 0.078 | 0.137 | 0.046 | 0.105 | 0.137 | 0.373 |
| hybrid | 0.078 | 0.157 | 0.052 | 0.108 | 0.157 | 0.373 |
| bm25 | 0.02 | 0.059 | 0.02 | 0.05 | 0.118 | 0.647 |

## Retrieval: answer-equivalent, question sentence only (51 questions)

The interviewer's turn without its preamble, closer to what a user types.

| System | P@1 | Hit@3 | P@3 | MRR@10 | Recall@10 | Drift@1 |
|---|---|---|---|---|---|---|
| semantic | 0.039 | 0.078 | 0.026 | 0.083 | 0.255 | 0.647 |
| chronus_pipeline | 0.059 | 0.118 | 0.046 | 0.082 | 0.118 | 0.647 |
| pipeline_no_importance | 0.039 | 0.078 | 0.026 | 0.056 | 0.078 | 0.667 |
| hybrid | 0.039 | 0.137 | 0.046 | 0.078 | 0.137 | 0.686 |
| bm25 | 0.078 | 0.118 | 0.039 | 0.107 | 0.157 | 0.686 |

Paper (Table IV, different corpus): semantic P@1 0.82, BM25 P@1 0.41.

## Match test (TED interview held out)

| Answer | Cosine to real answer | Content-word F1 |
|---|---|---|
| Mix Method (clone) | 0.376 | 0.06 |
| Random memory (baseline) | 0.08 | 0.013 |

## "I don't know" calibration

Best-match distance, answered questions: {'min': 0.226, 'median': 0.401, 'max': 0.592}; unanswerable questions: {'min': 0.463, 'median': 0.603, 'max': 0.73}.

- Current threshold 0.58: answers 97% of answerable, refuses 72% of unanswerable.
- Best balanced threshold 0.51: answers 85%, refuses 95% (chosen and measured on the same questions).
- Held out (chosen on half, measured on the other half, 4 splits; thresholds [0.49, 0.51, 0.51, 0.56]): answers 84%, refuses 91%.
