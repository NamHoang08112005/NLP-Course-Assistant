# Project Progress

## Implementation steps

| Step | Status |
|---|---|
| Create the Vietnamese course CFG and 229 input sentences | [x] |
| Implement CFG loading and sentence generation | [x] |
| Implement Earley parsing, semantic representation, intent and entity extraction | [x] |
| Connect both modules through `utils.test(**kwargs)` | [x] |
| Run the pipeline and verify all generated output files | [x] |
| Confirm protected instructor files are unchanged | [x] |

## Output files

| Output file | Status |
|---|---|
| `output/grammar.txt` | [x] |
| `output/samples.txt` | [x] |
| `output/parse-results.txt` | [x] |
| `output/semantic.txt` | [x] |
| `output/intent-entity.txt` | [x] |

## Verification notes

- Pipeline check: 229 inputs parsed; 124 produce parse trees and 105 produce `()`. `parse-results.txt`, `semantic.txt`, and `intent-entity.txt` match all 229 reference lines exactly. `samples.txt` contains 10,000 generated sentences, capped at the requested maximum.
- Docker fallback check: the bundled grammar matches `data/course_grammar.cfg`; with that file unavailable, all three parser output files still match the 229-line references.
- This workspace has no Git metadata, so `git status` is unavailable. SHA-256 comparisons confirmed the protected configuration files, `util.sh`, and all files under `java/` are unchanged.
