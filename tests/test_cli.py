#!/usr/bin/env python3
"""Command-line tests: run santa2026_verify.py as a user would (toy puzzles only, no competition data).
Run: python3 tests/test_cli.py"""
import csv, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "santa2026_verify.py")
TMP = tempfile.mkdtemp()
GOOD = [["/", 0, 0, 1], ["-", 0, 1, 2], ["+", 0, 2, 3], ["+", 0, 3, 4]]
fails = 0


def path(name):
    return os.path.join(TMP, name)


def write_rows(name, rows, header=("id", "program"), **kw):
    with open(path(name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, **kw)
        if header:
            w.writerow(header)
        for r in rows:
            w.writerow(r)
    return path(name)


def write_raw(name, data):
    with open(path(name), "wb") as f:
        f.write(data)
    return path(name)


PUZ = write_rows("puz.csv", [[f"t{i}", "[3]", "[1, 2, 5, 8]", 9, 48] for i in (1, 2, 3)],
                 header=("id", "starting_values", "targets", "value_limit", "registers"))
FULL = write_rows("full.csv", [[f"t{i}", json.dumps(GOOD, separators=(",", ":"))] for i in (1, 2, 3)])


def run(name, args, want_exit, want_text=(), env=None):
    global fails
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True, env=e)
    out = r.stdout + r.stderr
    bad = [t for t in want_text if t not in out]
    if r.returncode != want_exit or bad or "Traceback" in out:
        fails += 1
        print("FAIL", name, "exit", r.returncode, "missing", bad, "\n   ", out.strip().replace("\n", "\n    ")[:600])
    else:
        print("ok  ", name)


P = ["--puzzles", PUZ, "--allow-non-scored"]
run("valid toy file", [FULL] + P, 0, ["VALID puzzles=3 score=12"])
run("scored set required by default", [FULL, "--puzzles", PUZ], 1, ["HINT for practice_puzzles.csv"])
run("missing submission -> exit 2", [path("nope.csv")] + P, 2, ["cannot open submission"])
run("missing puzzles file -> exit 2", [FULL, "--puzzles", path("nope.csv")], 2, ["cannot read puzzles file"])
idx = write_rows("idx.csv", [["0", "t1", "[]"]], header=("", "id", "program"))
run("pandas index column hint", [idx] + P, 1, ["index=False"])
crcr = write_raw("crcr.csv", b"id,program\r\r\nt1,[]\r\r\n")
run("Windows doubled CR hint", [crcr] + P, 1, ["newline=''"])
semi = write_raw("semi.csv", b'"id";"program"\n"t1";"[]"\n')
run("semicolon separator hint", [semi] + P, 1, ["separator must be a comma"])
part = write_rows("part.csv", [["t2", json.dumps(GOOD)]])
run("--partial on a subset", [part, "--puzzles", PUZ, "--partial"], 0, ["PARTIAL VALID puzzles=1 score=4"])
run("subset without --partial suggests it", [part] + P, 1, ["--partial"])
hdr = write_rows("hdr.csv", [])
run("--partial on a header-only file", [hdr, "--puzzles", PUZ, "--partial"], 1, ["no data rows"])
run("--partial --compare against a full file", [part, "--puzzles", PUZ, "--partial", "--compare", FULL], 0,
    ["on 1 common puzzles", "equal on 1"])
run("--compare full vs full", [FULL] + P + ["--compare", FULL], 0, ["best-of-both would score 12"])
run("--trace", [FULL] + P + ["--trace", "t1"], 0, ["<- target", "done: 4 instructions"])
run("--trace unknown id", [FULL] + P + ["--trace", "zz"], 0, ["not in the puzzles file"])
run("--per-puzzle unwritable -> exit 2", [FULL] + P + ["--per-puzzle", path("no/such/dir/x.csv")], 2,
    ["could not write"])
run("--per-puzzle written", [FULL] + P + ["--per-puzzle", path("len.csv")], 0, ["VALID"])
spaces = write_rows("spaces.csv", [[f"t{i}", json.dumps(GOOD)] for i in (1, 2, 3)])
run("--canonical rejects spaced JSON", [spaces] + P + ["--canonical"], 1, ["separators"])
run("spaced JSON fine without --canonical", [spaces] + P, 0, ["VALID"])
big = write_rows("big.csv", [["t1", json.dumps([["+", 0, 0, 1]] * 4000, indent=40)], ["t2", "[]"], ["t3", "[]"]])
run("oversized cell reported as size, not CSV error", [big] + P, 1, ["bytes >"])
empty = write_rows("empty.csv", [["t1", ""], ["t2", "[]"], ["t3", "[]"]])
run("empty cell", [empty] + P, 1, ["empty program cell"])
nest = write_rows("nest.csv", [["t1", "[" * 3000 + "]" * 3000], ["t2", "[]"], ["t3", "[]"]])
run("deeply nested JSON does not crash", [nest] + P, 1, ["t1"])
uni = write_rows("uni.csv", [["t1", '[["−",0,0,1]]'], ["t2", "[]"], ["t3", "[]"]])
run("non-cp1252 output does not crash", [uni] + P, 1, ["bad op"], env={"PYTHONIOENCODING": "cp1252"})
neg = write_rows("neg.csv", [["t1", '[["/",-0,0,1],["-",0,1,2],["+",0,2,3],["+",0,3,4]]'], ["t2", "[]"], ["t3", "[]"]])
run("-0 rejected and flagged in trace", [neg] + P + ["--trace", "t1"], 1, ["negative numeric literal"])
print("FAILURES:", fails)
sys.exit(1 if fails else 0)
