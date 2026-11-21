# santa-2026-submission-verifier: a strict local verifier for Santa 2026 – The Elf Calculator

`santa2026_verify.py` is a single Python file (standard library only, Python ≥ 3.8) that checks a submission for the
Kaggle competition *Santa 2026 – The Elf Calculator* against the published rules and computes its score. This
README goes through the rules and explains why each check exists, so it also works as an introduction to the
problem.

No competition data files are included. The only competition content here is the small worked example from the
Data page, in `examples/`. You need your own copy of `puzzles.csv`.

```bash
python3 santa2026_verify.py submission.csv --puzzles puzzles.csv
# VALID puzzles=1000 score=...        (exit 0)   or   ERROR ... / REJECTED errors=N   (exit 1)

# any other puzzles file (practice_puzzles.csv, your own test puzzles) needs --allow-non-scored
python3 santa2026_verify.py my_practice_sub.csv --puzzles practice_puzzles.csv --allow-non-scored

# working on a few puzzles only? --partial checks just the ids that are in the file
python3 santa2026_verify.py ten_puzzles.csv --puzzles puzzles.csv --partial
```

When a file is rejected for a common reason, a `HINT` line explains how to fix it. The common reasons are:

- a pandas index column (use `df.to_csv(path, index=False)`);
- cells written with `str(program)` instead of `json.dumps(program)`;
- an Excel byte-order mark;
- checking a subset without `--partial`.

## The problem in one paragraph

Each puzzle gives some starting values in registers `0..k-1`, a list of target values and a `value_limit`. A
program is a list of instructions `[op, i, j, d]`, meaning *register d ← register i op register j*. There are 48
registers. A target counts as covered the moment it appears in any register. A puzzle is solved when every target
has been covered at least once. The score is the total number of instructions over all puzzles, and lower is
better. The challenge is to produce all the targets with as few arithmetic steps as possible, sharing intermediate
values between targets wherever you can.

Three details are easy to miss:

- **Both sources are read before the write.** So `d` may equal `i` or `j`: `["+", 0, 0, 0]` doubles register 0
  in place.
- **`i == j` is allowed.** `x / x = 1` gives you a 1 for free, and `x + x` doubles.
- **Starting registers can be overwritten.** After you have used a starting value, its register is just another
  free slot.

## What is checked, and why

| Clause | Check | Why it matters |
|---|---|---|
| File shape | Header exactly `id,program`; every puzzle id exactly once; no unknown ids; no extra columns | One missing or duplicated row makes the whole file invalid. |
| Cell size | Each program cell ≤ 131,072 UTF-8 bytes (measured after CSV unquoting) | Indented JSON can cross this limit before the 4,096-instruction limit does. Compact JSON stays far below it. |
| JSON | The cell is a JSON array of instructions, ≤ 4,096 of them | |
| Instruction | Exactly 4 elements; `op` ∈ `+ - * /`; `i, j, d` integers in `0..47` | |
| Defined sources | Both source registers must already hold a value | Only registers `0..len(start)-1` start out filled. Reading an empty register is illegal. |
| Positive results | Every result must be ≥ 1 | `a - b` needs `a > b`, so `a - a = 0` is illegal. |
| Exact division | `/` is allowed only when `b` divides `a` exactly | There is no floor division. |
| Value limit | Every result must be ≤ `value_limit`, including intermediate values | Going over the limit and dividing back down is still illegal. |
| Coverage | A target is covered if it is in any register at any time, including at the start | Overwriting a target later doesn't uncover it. A target that is already a starting value costs nothing. |
| Counting | Every instruction counts, including ones after all targets are covered | Trailing dead instructions cost score, so clean them up. |

### Conservative extras

The rules pages don't spell these cases out. The verifier rejects them anyway, so it is meant to be at least as
strict as the real scorer:

- register indices given as `true`/`false` or `1.0`. In Python `True == 1`, so a careless checker would accept
  them;
- a UTF-8 byte-order mark (BOM) at the start of the file;
- NUL bytes;
- bare `\r` line endings (the `\r\n` that Python's `csv.writer` writes is fine);
- negative numeric literals such as `-0`. JSON parses `-0` to the integer `0`, so a register written as `-0` would
  silently pass a naive checker;
- malformed CSV quoting (the file is parsed with `strict=True`);
- blank lines.

It also checks the puzzles file you point it at: for the scored set it must be exactly `scored_0001..scored_1000`,
with 48 registers and `1 ≤ value_limit ≤ 10^18`.

`--canonical` additionally requires every cell to be compact JSON, i.e. exactly
`json.dumps(program, separators=(",", ":"))`. This is useful as a pre-submission gate when you combine files from
several tools.

**How well does it match Kaggle?** On the author's own submissions so far (four files), the local score has equalled
the leaderboard score every time. That is evidence for the common cases, not proof for every edge case.

## Extra commands

```bash
# per-puzzle instruction counts (written only when the file is valid)
python3 santa2026_verify.py sub.csv --puzzles puzzles.csv --per-puzzle lengths.csv

# compare two submissions: counts of shorter/longer/equal puzzles, the largest differences either way,
# and what a per-puzzle best-of-both would score. --show N sets how many differences are listed.
# The second file is always checked without --canonical.
python3 santa2026_verify.py mine.csv --puzzles puzzles.csv --compare other.csv --show 10

# watch one program run, register by register (useful for learning and for finding an ILLEGAL step)
python3 santa2026_verify.py examples/toy_submission.csv --puzzles examples/toy_puzzles.csv --allow-non-scored --trace example_0001
# start [3]  targets left 4  limit 9
#     0  r1 = r0 / r0 = 3 / 3 = 1   <- target
#     1  r2 = r0 - r1 = 3 - 1 = 2   <- target
#     2  r3 = r0 + r2 = 3 + 2 = 5   <- target
#     3  r4 = r0 + r3 = 3 + 5 = 8   <- target
# done: 4 instructions, 0 targets not covered
# VALID puzzles=1 score=4
```

Step numbers in traces and error messages are 0-based. The Data page's table counts from 1.

Exit status:

- `0`: valid;
- `1`: the submission is invalid;
- `2`: usage problem, such as an unreadable puzzles file, a missing submission file, or a `--per-puzzle` file that could not be written.

The exit status reflects only the main submission, even when `--compare` reports the other file as invalid.

From Python:

```python
from santa2026_verify import load_puzzles, check_program, verify_file
P = load_puzzles("puzzles.csv")   # {id: {"start": [...], "targets": [...], "limit": int, "registers": int}}
ok, msg = check_program(P["scored_0001"], program)      # one program (lists or tuples) -> (bool, reason)
ok, score, errors, lengths = verify_file("sub.csv", P)   # whole file; never raises on a malformed submission
# verify_file requires the full scored set by default, like the command line.
# For practice puzzles or a subset pass require_scored=False; such a file is then valid only for that puzzle set.
```

`check_program` is fine for checking finished programs. It allocates per call, so don't use it as the inner loop of a
search.

## Writing a valid submission

```python
import csv, json
with open("submission.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "program"])
    for pid, prog in programs.items():               # prog = [["+", 0, 0, 1], ...]
        w.writerow([pid, json.dumps(prog, separators=(",", ":"))])
# pandas: df.to_csv("submission.csv", index=False)  with the program column already json.dumps()-ed strings
# R:      write.csv(df, "submission.csv", row.names = FALSE)
```

Common mistakes:

- writing `str(program)` (single quotes, not JSON);
- leaving the pandas index on;
- saving through Excel, which can add a BOM or switch to `;` as the separator;
- on Windows, opening the file without `newline=""` when using `csv.writer`, which produces `\r\r\n` line endings.

## Tests

`tests/test_santa2026_verify.py` has 66 cases:

- 47 broken programs or files that must be rejected;
- 14 valid edge cases that must pass;
- 5 checks of the Python API contract.

`tests/test_cli.py` runs the command line the way a user would: exit codes, hints, `--partial`, `--compare`, `--trace`, `--per-puzzle`, `--canonical`, oversized and empty cells, Windows line endings and a cp1252 console. For the program-level cases, the test also
fails if a broken program is rejected only because a target is missing, so each one has to break the rule it was
written for. The file-level cases check only that the file is rejected. The test also requires a few valid edge
cases to pass: the Data page's worked example, register 47, exactly 4,096 instructions, and a result equal to
`value_limit`.

```bash
python3 tests/test_santa2026_verify.py
python3 tests/test_cli.py
# optional anchor against the official sample (its longest program has 2873 instructions):
ELF_PUZZLES=puzzles.csv ELF_SAMPLE=sample_submission.csv python3 tests/test_santa2026_verify.py
```

On Windows use `py` (or `python`) instead of `python3`. Set the variables first:

- PowerShell: `$env:ELF_PUZZLES="puzzles.csv"; $env:ELF_SAMPLE="sample_submission.csv"; py tests\test_santa2026_verify.py`
- cmd: `set ELF_PUZZLES=puzzles.csv` and `set ELF_SAMPLE=sample_submission.csv`, then `py tests\test_santa2026_verify.py`

If you find a file that this verifier accepts and Kaggle rejects, or the other way round, please open an issue.
Those disagreements are exactly the cases it should learn from.

## License

MIT. See `LICENSE`.
