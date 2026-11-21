#!/usr/bin/env python3
"""Mutation tests for santa2026_verify.py: deliberately broken programs and files must be rejected for the right
reason, and the worked example from the competition's Data page must pass.
Run: python3 tests/test_santa2026_verify.py
Optional anchor: set ELF_PUZZLES=path/to/puzzles.csv and ELF_SAMPLE=path/to/sample_submission.csv."""
import csv, json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from santa2026_verify import check_program, verify_file

EX = dict(start=[3], targets=[1, 2, 5, 8], limit=9, registers=48)
GOOD = [["/", 0, 0, 1], ["-", 0, 1, 2], ["+", 0, 2, 3], ["+", 0, 3, 4]]
fails = 0

def expect(name, ok_expected, puz, prog):
    global fails
    ok, msg = check_program(puz, prog)
    if not ok and not ok_expected and "not covered" in msg and not any(w in name for w in ("missing target", "empty program")):
        fails += 1; print("FAIL (vacuous: rejected only for coverage)", name, msg); return
    if ok != ok_expected:
        fails += 1
        print("FAIL", name, msg)
    else:
        print("ok  ", name, "->", msg)

expect("worked example", True, EX, GOOD)
expect("dest==source allowed", True, dict(EX, targets=[6]), [["+", 0, 0, 0]])
expect("all targets in start, empty program", True, dict(EX, targets=[3]), [])
expect("limit+1", False, dict(EX, targets=[1, 2, 5, 8, 10]), GOOD + [["+", 1, 4, 5], ["+", 3, 3, 6]])
expect("result > limit (3+3+3=... 3*3=9 ok, 9+3=12>9)", False, dict(EX, targets=[12]), [["*", 0, 0, 1], ["+", 1, 0, 2]])
expect("result == limit accepted", True, dict(EX, targets=[9]), [["*", 0, 0, 1]])
expect("intermediate overshoot then divide", False, dict(EX, targets=[5]), [["*", 0, 0, 1], ["+", 1, 0, 1], ["/", 1, 0, 2]])
expect("illegal instruction after coverage", False, dict(EX, targets=[3]), [["-", 0, 0, 1]])
expect("register 47 accepted", True, dict(EX, targets=[6]), [["+", 0, 0, 47]])
expect("bad source register i=48", False, EX, [["+", 48, 0, 1]])
expect("bad source register j=-1", False, EX, [["+", 0, -1, 1]])
expect("bool source False", False, EX, [["+", False, 0, 1]])
expect("None register", False, EX, [["+", 0, None, 1]])
expect("nested register [0]", False, EX, [["+", [0], 0, 1]])
expect("read undefined dest-as-source", False, EX, [["+", 5, 0, 5]])
expect("division a<b inexact", False, dict(EX, targets=[1]), [["/", 0, 0, 1], ["/", 1, 0, 2]])
expect("exact division 6/2=3 path", True, dict(start=[6, 2], targets=[3], limit=9, registers=48), [["/", 0, 1, 2]])
expect("empty program, target missing", False, EX, [])
expect("multi-start order", True, dict(start=[2, 5], targets=[7], limit=9, registers=48), [["+", 0, 1, 2]])
expect("overwrite start that is a target stays covered", True, dict(start=[2, 5], targets=[2, 7], limit=9, registers=48), [["+", 0, 1, 0]])
expect("product 1e20 above a 1e18 limit", False, dict(start=[10**10], targets=[1], limit=10**18, registers=48), [["*", 0, 0, 1]])
expect("a-b with a==b", False, dict(EX, targets=[1]), [["-", 0, 0, 1]])
expect("a-b negative", False, EX, [["/", 0, 0, 1], ["-", 1, 0, 2]])
expect("inexact division", False, dict(EX, targets=[1]), [["/", 0, 0, 1], ["+", 0, 1, 2], ["/", 2, 0, 3]])
expect("undefined source", False, EX, [["+", 0, 5, 1]])
expect("register 48", False, EX, [["+", 0, 0, 48]])
expect("register -1", False, EX, [["+", 0, 0, -1]])
expect("float register 1.0", False, EX, [["/", 0, 0, 1.0]])
expect("bool register true", False, EX, [["/", 0, 0, True]])
expect("string register", False, EX, [["/", 0, 0, "1"]])
expect("5-element instr", False, EX, [["/", 0, 0, 1, 2]])
expect("3-element instr", False, EX, [["/", 0, 0]])
expect("bad op x", False, EX, [["x", 0, 0, 1]])
expect("bad op //", False, EX, [["//", 0, 0, 1]])
expect("missing target", False, EX, GOOD[:3])
expect("4097 instructions", False, dict(EX, targets=[3]), [["/", 0, 0, 1]] * 4097)
expect("4096 instructions ok", True, dict(EX, targets=[3]), [["/", 0, 0, 1]] * 4096)
expect("program not a list", False, EX, {"a": 1})
expect("instr not a list (4-char string)", False, EX, ["+001"])
expect("target only overwritten later still counts", True, dict(EX, targets=[6]), [["+", 0, 0, 1], ["/", 0, 0, 1]])

# file-level cases
P = {"a": dict(EX), "b": dict(EX, targets=[3])}
def filecase(name, ok_expected, rows, header=("id", "program"), want_score=None):
    global fails
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
        w = csv.writer(f); w.writerow(header)
        for r in rows: w.writerow(r)
    ok, score, errs, _ = verify_file(f.name, P, require_scored=False)
    os.unlink(f.name)
    if ok and want_score is not None and score != want_score:
        fails += 1; print("FAIL", name, "score", score, "!=", want_score); return
    if ok != ok_expected:
        fails += 1; print("FAIL", name, errs[:2])
    else:
        print("ok  ", name, "->", score if ok else errs[:1])
g = json.dumps(GOOD)
filecase("file ok, score 4", True, [["a", g], ["b", "[]"]], want_score=4)
filecase("row order irrelevant", True, [["b", "[]"], ["a", g]], want_score=4)
filecase("post-coverage instructions counted", True, [["a", g], ["b", json.dumps([["+", 0, 0, 1]])]], want_score=5)
filecase("negative zero register", False, [["a", g], ["b", '[["+",-0,0,1]]']])
filecase("missing id", False, [["a", g]])
filecase("duplicate id", False, [["a", g], ["b", "[]"], ["b", "[]"]])
filecase("extra unknown id", False, [["a", g], ["b", "[]"], ["practice_0001", "[]"]])
filecase("extra column", False, [["a", g, "x"], ["b", "[]"]])
filecase("header swapped", False, [[g, "a"], ["[]", "b"]], header=("program", "id"))
filecase("bad json", False, [["a", "[[\"+\",0,0,1]"], ["b", "[]"]])
filecase("cell > 131072 bytes", False, [["a", g], ["b", json.dumps([["/", 0, 0, 1]] * 4000, indent=8)]])
def rawcase(name, data, puzzles=P, require_scored=False):
    global fails
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write(data)
    ok, score, errs, _ = verify_file(f.name, puzzles, require_scored=require_scored)
    os.unlink(f.name)
    if ok: fails += 1; print("FAIL", name, "accepted")
    else: print("ok  ", name, "->", errs[:1])
PB = dict(EX, targets=[3])
P1 = {"a": PB}
rawcase("empty file", b"", P1)
rawcase("invalid utf-8", b"id,program\na,[]\xff\n", P1)
rawcase("NUL byte", b"id,program\na,[]\x00\n", P1)
rawcase("UTF-8 BOM", b"\xef\xbb\xbfid,program\na,[]\n", P1)
rawcase("bare CR", b"id,program\ra,[]\r", P1)
rawcase("unclosed quote", b'id,program\na,"[]', P1)
rawcase("text after closing quote", b'id,program\na,"["]\n', P1)
rawcase("blank line", b"id,program\na,[]\n\n", P1)
rawcase("non-scored id set when required", b"id,program\na,[]\n", P1, require_scored=True)
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
    w = csv.writer(f); w.writerow(["id", "program"]); w.writerow(["a", "[]"])
okc, sc, _, _ = verify_file(f.name, P1, require_scored=False); os.unlink(f.name)
if not (okc and sc == 0): fails += 1; print("FAIL csv.writer CRLF file rejected")
else: print("ok   csv.writer CRLF file accepted")
# API contract cases (user-facing): default requires the scored set; tuples accepted; bad puzzles arg reported
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
    w = csv.writer(f); w.writerow(["id", "program"]); w.writerow(["a", "[]"])
okd, _, errd, _ = verify_file(f.name, P1)
okp, _, errp, _ = verify_file(f.name, "puzzles.csv")
okm, _, errm, _ = verify_file(os.path.join(tempfile.gettempdir(), "no_such_submission_xyz.csv"), P1, require_scored=False)
os.unlink(f.name)
for name, cond in [("default require_scored rejects a non-scored puzzle set", not okd and "scored" in errd[0]),
                   ("puzzles passed as a path string is reported, not crashed", not okp and "load_puzzles" in errp[0]),
                   ("missing submission file is reported", not okm and "cannot open" in errm[0]),
                   ("tuple instructions accepted by check_program", check_program(EX, [tuple(x) for x in GOOD])[0]),
                   ("zero start value puzzle reported, not crashed",
                    verify_file(__file__, {"a": dict(EX, start=[0])}, require_scored=False)[2][0].startswith("puzzle"))]:
    if cond: print("ok  ", name)
    else: fails += 1; print("FAIL", name)
# optional anchor (needs the competition files, which are NOT shipped here): the official sample must be valid
# and its longest program has 2873 instructions (stated on the Evaluation page)
from santa2026_verify import load_puzzles
PZP, SMP = os.environ.get("ELF_PUZZLES"), os.environ.get("ELF_SAMPLE")
if PZP and SMP:
    PZ = load_puzzles(PZP)
    oks, scs, _, lns = verify_file(SMP, PZ, require_scored=True)
    if not (oks and max(lns.values()) == 2873): fails += 1; print("FAIL sample anchor", oks, scs)
    else: print("ok   sample anchor valid, max len 2873, score", scs)
else:
    print("skip sample anchor (set ELF_PUZZLES and ELF_SAMPLE to run it)")
print("FAILURES:", fails)
sys.exit(1 if fails else 0)
