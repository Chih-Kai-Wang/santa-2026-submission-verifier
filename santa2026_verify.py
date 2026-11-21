#!/usr/bin/env python3
"""santa2026_verify - strict, dependency-free verifier and scorer for Kaggle "Santa 2026 - The Elf Calculator".

Checks (each mirrors a clause of the public Data / Evaluation pages; see README for the reasoning):
  * CSV: exactly the columns id,program in that order; every puzzle id exactly once, no extras.
  * program cell: UTF-8 <= 131072 bytes; a JSON array; <= 4096 instructions.
  * instruction: 4-element array [op, i, j, d]; op in + - * /; i, j, d integers in 0..47.
  * sources must hold a value (registers 0..len(start)-1 start defined, the rest empty).
  * result must be a positive integer <= value_limit; '-' only if a > b; '/' only if b divides a exactly.
  * a target counts as covered if it appears in any register at any time (including at the start).
Conservative extras (beyond what the pages state; meant to be at least as strict as the real scorer):
  bool/float register indices, UTF-8 BOM, NUL bytes, bare CR line endings, negative numeric literals such as -0,
  malformed CSV quoting, blank lines. For the scored set the puzzles file must be exactly scored_0001..scored_1000
  with 48 registers and 1 <= value_limit <= 1e18.

Usage:
  python3 santa2026_verify.py SUBMISSION.csv --puzzles puzzles.csv [--per-puzzle out.csv] [--canonical]
  python3 santa2026_verify.py SUBMISSION.csv --puzzles practice_puzzles.csv --allow-non-scored
  python3 santa2026_verify.py SUBMISSION.csv --puzzles puzzles.csv --partial          # only ids in the file
  python3 santa2026_verify.py SUBMISSION.csv --puzzles puzzles.csv --compare OTHER.csv
  python3 santa2026_verify.py SUBMISSION.csv --puzzles puzzles.csv --trace ID
Exit status: 0 valid, 1 invalid submission, 2 usage error (unreadable puzzles file, missing submission file).
Standard library only (Python >= 3.8).
"""
import argparse, csv, io, json, re, sys

NREG = 48
MAX_INSTR = 4096
MAX_BYTES = 131072
OPS = {"+", "-", "*", "/"}
SCORED_IDS = frozenset(f"scored_{i:04d}" for i in range(1, 1001))
NEG_NUM = re.compile(r'(?<!")-\s*\d')   # negative numeric literal (e.g. JSON -0) -> reject conservatively
if csv.field_size_limit() < 2**31 - 1:
    csv.field_size_limit(2**31 - 1)   # an oversized cell must reach the size check, not crash the reader


def _short(x, n=120):
    s = x if isinstance(x, str) else repr(x)
    return s if len(s) <= n else s[:n] + "..."


def load_puzzles(path):
    """Read a puzzles CSV (id,starting_values,targets,value_limit,registers[,...]) into
    {id: {"start": [...], "targets": [...], "limit": int, "registers": int}}. Extra columns are ignored.
    Raises ValueError on duplicate ids or missing columns."""
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        need = {"id", "starting_values", "targets", "value_limit", "registers"}
        if not rd.fieldnames or not need <= set(rd.fieldnames):
            raise ValueError(f"puzzles file needs columns {sorted(need)}, got {rd.fieldnames}")
        for r in rd:
            if r["id"] in out:
                raise ValueError(f"duplicate puzzle id {r['id']!r}")
            out[r["id"]] = dict(
                start=[int(x) for x in json.loads(r["starting_values"])],
                targets=[int(x) for x in json.loads(r["targets"])],
                limit=int(r["value_limit"]),
                registers=int(r["registers"]),
            )
    return out


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_program(puz, prog):
    """Replay one program on one puzzle. prog: list of [op, i, j, d] (lists or tuples).
    Returns (ok, message); never raises for a well-formed puzzle dict."""
    if not isinstance(prog, (list, tuple)):
        return False, "program is not a JSON array"
    if len(prog) > MAX_INSTR:
        return False, f"too many instructions ({len(prog)} > {MAX_INSTR})"
    nreg = puz.get("registers", NREG)
    lim = puz["limit"]
    regs = [None] * nreg
    for k, v in enumerate(puz["start"]):
        regs[k] = v
    need = set(puz["targets"])
    need.difference_update(v for v in regs if v is not None)
    for step, ins in enumerate(prog):
        if not isinstance(ins, (list, tuple)) or len(ins) != 4:
            return False, f"step {step}: instruction is not a 4-element array: {_short(ins)}"
        op, i, j, d = ins
        if not isinstance(op, str) or op not in OPS:
            return False, f"step {step}: bad op {op!r} (use one of + - * /)"
        for x in (i, j, d):
            if not _is_int(x) or not (0 <= x < nreg):
                return False, f"step {step}: bad register {x!r} (integers 0..{nreg - 1})"
        a, b = regs[i], regs[j]
        if a is None or b is None:
            return False, f"step {step}: reads empty register r{i if a is None else j}"
        if op == "+":
            r = a + b
        elif op == "-":
            if not a > b:
                return False, f"step {step}: non-positive subtraction {a} - {b}"
            r = a - b
        elif op == "*":
            r = a * b
        else:
            if a % b != 0:
                return False, f"step {step}: inexact division {a} / {b}"
            r = a // b
        if r <= 0:
            return False, f"step {step}: non-positive result {r}"
        if r > lim:
            return False, f"step {step}: value {r} exceeds limit {lim}"
        regs[d] = r
        need.discard(r)
    if need:
        return False, f"{len(need)} targets not covered, e.g. {sorted(need)[:3]}"
    return True, "ok"


def _check_puzzles(puzzles, require_scored):
    """Validate the puzzles mapping itself; returns a list of problems (empty if fine)."""
    if not isinstance(puzzles, dict):
        return [f"puzzles must be the dict returned by load_puzzles(), got {type(puzzles).__name__}"]
    if not puzzles:
        return ["puzzles is empty"]
    probs = []
    for k, q in puzzles.items():
        try:
            st, tg, lim, nreg = q["start"], q["targets"], q["limit"], q["registers"]
            if (not _is_int(lim) or lim < 1 or not _is_int(nreg) or not (1 <= len(st) <= nreg)
                    or any(not _is_int(v) or v < 1 for v in list(st) + list(tg))):
                probs.append(f"puzzle {k!r} is malformed (integer limit >= 1 and registers, positive integer "
                             "start/targets, 1 <= len(start) <= registers)")
        except (KeyError, TypeError):
            probs.append(f"puzzle {k!r} lacks start/targets/limit/registers (use load_puzzles())")
        if len(probs) >= 3:
            break
    if require_scored and not probs:
        if set(puzzles) != SCORED_IDS:
            probs.append("puzzle file is not exactly scored_0001..scored_1000")
        else:
            bad = [k for k, q in puzzles.items() if q["registers"] != NREG or not (1 <= q["limit"] <= 10**18)]
            if bad:
                probs.append(f"puzzle spec out of range (registers != 48 or limit outside 1..1e18): {bad[:3]}")
    return probs


def verify_file(sub_path, puzzles, require_scored=True, canonical=False):
    """Check a whole submission file. Returns (ok, score, errors, lengths):
      ok       True iff the file is valid;
      score    total instruction count if ok, else None;
      errors   list of human-readable problems (empty if ok);
      lengths  {id: instruction count} for every program that passed (partial when ok is False).
    require_scored=True (default, like the command line) also requires `puzzles` to be exactly the scored set,
    so a file checked against practice puzzles or a subset is never reported as submittable.
    Never raises because of the submission's content; a bad `puzzles` argument is reported in errors."""
    probs = _check_puzzles(puzzles, require_scored)
    if probs:
        return False, None, probs, {}
    try:
        with open(sub_path, "rb") as f:
            raw = f.read()
    except OSError as e:
        return False, None, [f"cannot open submission: {type(e).__name__}: {e}"], {}
    errors, lens = [], {}
    if raw.startswith(b"\xef\xbb\xbf"):
        return False, None, ["UTF-8 BOM present"], lens
    if b"\x00" in raw:
        return False, None, ["NUL byte present"], lens
    if b"\r\r\n" in raw:
        return False, None, ["doubled CR line endings (\\r\\r\\n)"], lens
    if re.search(rb"\r(?!\n)", raw):
        return False, None, ["bare CR line ending"], lens
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return False, None, [f"file is not valid UTF-8 ({e})"], lens
    rd = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(rd, None)
        if header != ["id", "program"]:
            return False, None, [f"bad header {_short(header)}"], lens
        seen = set()
        for row in rd:
            line = rd.line_num
            if len(row) != 2:
                errors.append(f"line {line}: expected 2 columns (id,program), got {len(row)}")
                continue
            pid, cell = row
            if pid in seen:
                errors.append(f"line {line}: duplicate id {pid!r}")
                continue
            seen.add(pid)
            if pid not in puzzles:
                errors.append(f"line {line}: unknown id {pid!r}")
                continue
            nbytes = len(cell.encode("utf-8"))
            if nbytes > MAX_BYTES:
                errors.append(f"{pid}: cell is {nbytes} bytes > {MAX_BYTES}")
                continue
            if not cell.strip():
                errors.append(f"{pid}: empty program cell (use [] for a puzzle whose targets are all starting values)")
                continue
            try:
                prog = json.loads(cell)
            except (ValueError, RecursionError) as e:
                errors.append(f"{pid}: bad JSON {_short(str(e))}")
                continue
            ok, msg = check_program(puzzles[pid], prog)
            if not ok:
                errors.append(f"{pid}: {msg}")
                continue
            if NEG_NUM.search(cell):
                errors.append(f"{pid}: negative numeric literal such as -0 (write plain non-negative integers)")
                continue
            if canonical and cell != json.dumps(prog, separators=(",", ":")):
                errors.append(f"{pid}: program cell is not compact canonical JSON")
                continue
            lens[pid] = len(prog)
    except csv.Error as e:
        first = text.split("\n", 1)[0]
        if rd.line_num <= 1 and ";" in first and "," not in first:
            errors.append("header uses ';' as separator")
        else:
            errors.append(f"line {rd.line_num}: malformed CSV ({e})")
        return False, None, errors, lens
    missing = set(puzzles) - seen
    if missing:
        errors.append(f"{len(missing)} ids missing, e.g. {sorted(missing)[:3]}")
    ok = not errors
    return ok, (sum(lens.values()) if ok else None), errors, lens


def trace(puz, prog, out=None):
    """Print a step-by-step register trace of one program (0-based step numbers)."""
    out = out or sys.stdout
    regs = [None] * puz.get("registers", NREG)
    for k, v in enumerate(puz["start"]):
        regs[k] = v
    need = set(puz["targets"]) - {v for v in regs if v is not None}
    print(f"start {puz['start']}  targets left {len(need)}  limit {puz['limit']}", file=out)
    ok, msg = check_program(dict(puz, targets=[]), prog)
    bad = int(msg.split()[1].rstrip(":")) if not ok and msg.startswith("step ") else None
    if not ok and bad is None:
        print("ILLEGAL:", msg, file=out)
        return
    for step, ins in enumerate(prog):
        if step == bad:
            print(f"{step:5d}  {ins}   ILLEGAL: {msg.split(': ', 1)[-1]}", file=out)
            return
        op, i, j, d = ins
        a, b = regs[i], regs[j]
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        else:
            r = a // b
        regs[d] = r
        hit = r in need
        need.discard(r)
        print(f"{step:5d}  r{d} = r{i} {op} r{j} = {a} {op} {b} = {r}" + ("   <- target" if hit else ""), file=out)
    print(f"done: {len(prog)} instructions, {len(need)} targets not covered", file=out)


HINTS = [
    ("bad header ['', 'id', 'program']", "this looks like a pandas index column: write with df.to_csv(path, index=False)"),
    ("bad header ['id;program']", "semicolon-separated file (Excel locale?): the separator must be a comma"),
    ("header uses ';'", "semicolon-separated file (Excel locale, R write.csv2?): the separator must be a comma"),
    ("doubled CR", "on Windows open the file with newline='' when using csv.writer: open(path, 'w', newline='')"),
    ("UTF-8 BOM present", "Excel 'CSV UTF-8' and encoding='utf-8-sig' add a BOM. Kaggle's reader may well accept it, "
                          "but this verifier is conservative; re-save with plain encoding='utf-8' to be safe"),
    ("bad JSON Expecting property name", "cells must be JSON: use json.dumps(program), not str(program)"),
    ("bad JSON Expecting value", "cells must be JSON (double quotes, e.g. [[\"+\",0,0,1]]): use json.dumps(program), "
                                 "not str(program)"),
    ("malformed CSV", "write the file with csv.writer or pandas, which quote the JSON cell correctly"),
    ("expected 2 columns", "the JSON cell must be quoted (csv.writer / pandas do this); a blank line also counts here"),
    ("ids missing", "checking only some puzzles? add --partial to verify just the ids present in the file"),
    ("puzzle file is not exactly scored", "for practice_puzzles.csv or your own puzzles add --allow-non-scored"),
    ("not compact canonical JSON", "only with --canonical: write cells with json.dumps(program, separators=(',', ':'))"),
    ("bare CR line ending", "old Mac line endings: re-save with \\n or \\r\\n line endings"),
]


def _hints(errors, partial=False):
    shown = set()
    for e in errors:
        for pat, hint in HINTS:
            if partial and "--partial" in hint:
                continue
            if pat in e and hint not in shown:
                shown.add(hint)
                print("HINT", hint)


def _ids_in(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return {r[0] for r in list(csv.reader(f))[1:] if r}
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def _trace_cli(path, pid, puzzles):
    if pid not in puzzles:
        print(f"TRACE: {pid!r} is not in the puzzles file")
        return
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = [r for n, r in enumerate(csv.reader(f)) if n > 0 and r and r[0] == pid]
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        print(f"TRACE: cannot read submission ({type(e).__name__})")
        return
    if not rows:
        print(f"TRACE: {pid!r} not found in submission")
        return
    probs = _check_puzzles({pid: puzzles[pid]}, False)
    if probs:
        print(f"TRACE: cannot trace, {probs[0]}")
        return
    for n, row in enumerate(rows):
        if len(rows) > 1:
            print(f"TRACE: occurrence {n + 1} of {len(rows)}")
        if len(row) != 2:
            print(f"TRACE: row has {len(row)} columns, expected 2")
            continue
        try:
            prog = json.loads(row[1])
        except (ValueError, RecursionError):
            print("TRACE: cell is not valid JSON")
            continue
        trace(puzzles[pid], prog)
        if NEG_NUM.search(row[1]):
            print("TRACE: note: the cell contains a negative numeric literal such as -0, which this verifier rejects")


def main():
    ap = argparse.ArgumentParser(description="Strict verifier/scorer for Santa 2026 - The Elf Calculator")
    ap.add_argument("submission")
    ap.add_argument("--puzzles", required=True, help="the competition's puzzles.csv (or practice_puzzles.csv)")
    ap.add_argument("--per-puzzle", help="write id,n (instruction count) when the file is valid")
    ap.add_argument("--canonical", action="store_true",
                    help="also require compact JSON cells (json.dumps(program, separators=(',', ':')))")
    ap.add_argument("--allow-non-scored", action="store_true",
                    help="accept a puzzles file other than exactly scored_0001..scored_1000 (e.g. practice puzzles)")
    ap.add_argument("--partial", action="store_true",
                    help="check only the puzzle ids that appear in the submission (score = sum over those ids)")
    ap.add_argument("--compare", help="second submission: per-puzzle comparison (always checked without --canonical)")
    ap.add_argument("--show", type=int, default=10, help="with --compare: how many largest differences to list")
    ap.add_argument("--trace", help="print a register trace for this puzzle id")
    a = ap.parse_args()
    a.show = max(0, a.show)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")   # never crash on a console that cannot print a character
    try:
        puzzles = load_puzzles(a.puzzles)
    except Exception as e:  # any problem with the puzzles file is a usage error
        print(f"ERROR cannot read puzzles file: {type(e).__name__}: {e}")
        sys.exit(2)
    all_puzzles = puzzles
    req = not (a.allow_non_scored or a.partial)

    def subset(path):
        ids = _ids_in(path)
        return {k: v for k, v in all_puzzles.items() if k in ids} if ids else None

    if a.partial:
        sub = subset(a.submission)
        if sub is None:
            print("ERROR the submission has no data rows (or cannot be read)")
            print("REJECTED errors=1")
            sys.exit(1)
        puzzles = sub
        print(f"PARTIAL checking {len(puzzles)} puzzles (the ids present in the submission); "
              "a partial file is not a complete submission")
    ok, score, errors, lens = verify_file(a.submission, puzzles, require_scored=req, canonical=a.canonical)
    for e in errors[:20]:
        print("ERROR", e)
    if len(errors) > 20:
        print(f"ERROR ... and {len(errors) - 20} more")
    _hints(errors, a.partial)
    if errors and errors[0].startswith("cannot open submission"):
        sys.exit(2)
    if a.trace:
        _trace_cli(a.submission, a.trace, all_puzzles)
    if a.compare:
        if not ok:
            print("COMPARE skipped: the main submission is not valid")
        else:
            p2 = (subset(a.compare) or {}) if a.partial else puzzles
            ok2, score2, err2, lens2 = (verify_file(a.compare, p2, require_scored=req) if p2
                                        else (False, None, ["no readable data rows"], {}))
            if not ok2:
                print(f"COMPARE skipped: {a.compare} is not valid ({len(err2)} errors), e.g. {err2[:1]}")
            else:
                common = [k for k in lens if k in lens2]
                if len(common) < len(lens):
                    print(f"COMPARE note: {a.compare} lacks {len(lens) - len(common)} of this file's puzzles; "
                          "comparing the common ones only")
                diff = sorted((lens[k] - lens2[k], k) for k in common if lens[k] != lens2[k])
                better = [x for x in diff if x[0] < 0]
                worse = [x for x in diff if x[0] > 0][::-1]
                print(f"COMPARE {a.submission} vs {a.compare} on {len(common)} common puzzles "
                      f"({sum(lens[k] for k in common)} vs {sum(lens2[k] for k in common)}): shorter on {len(better)}, "
                      f"longer on {len(worse)}, equal on {len(common) - len(diff)}; "
                      f"best-of-both would score {sum(min(lens[k], lens2[k]) for k in common)}")
                for title, rows in (("largest improvements", better), ("largest regressions", worse)):
                    if rows and a.show:
                        print(f"  {title}:")
                        for d, k in rows[:a.show]:
                            print(f"    {k}: {lens[k]} vs {lens2[k]} ({d:+d})")
    if ok and a.per_puzzle:
        try:
            with open(a.per_puzzle, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "n"])
                for k in sorted(lens):
                    w.writerow([k, lens[k]])
        except (OSError, ValueError) as e:
            print(f"ERROR could not write {a.per_puzzle}: {e}")
            print(f"VALID puzzles={len(lens)} score={score} (but the per-puzzle file was not written)")
            sys.exit(2)
    if ok:
        print(f"{'PARTIAL VALID' if a.partial else 'VALID'} puzzles={len(lens)} score={score}")
        sys.exit(0)
    print(f"REJECTED errors={len(errors)}")
    sys.exit(1)


if __name__ == "__main__":
    main()
