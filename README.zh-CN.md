# santa-2026-submission-verifier：适用于 Santa 2026 – The Elf Calculator 的严格本地校验器

[English](README.md) · [繁體中文](README.zh-TW.md) · **简体中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md)

`santa2026_verify.py` 是单个 Python 文件（仅依赖标准库，需要 Python ≥ 3.8），用于依据公开规则校验 Kaggle 竞赛 *Santa 2026 – The Elf Calculator* 的提交文件，并计算其得分。本 README 会逐条梳理规则并解释每项检查存在的原因，因此也适合作为这道题的入门介绍。

本仓库不包含竞赛数据文件。这里唯一附带的竞赛内容是来自 Data 页面的小型示例，位于 `examples/` 目录中。你需要自行准备 `puzzles.csv`。

```bash
python3 santa2026_verify.py submission.csv --puzzles puzzles.csv
# VALID puzzles=1000 score=...        （退出码 0） 或   ERROR ... / REJECTED errors=N   （退出码 1）

# 任何其他题目文件（如 practice_puzzles.csv 或你自己的测试题）都需要加上 --allow-non-scored
python3 santa2026_verify.py my_practice_sub.csv --puzzles practice_puzzles.csv --allow-non-scored

# 只在做其中几道题？--partial 只会检查文件里包含的题目 id
python3 santa2026_verify.py ten_puzzles.csv --puzzles puzzles.csv --partial
```

当文件因常见原因被拒收时，程序会输出一行 `HINT` 说明如何修复。常见原因包括：

- 多了 pandas 索引列（请改用 `df.to_csv(path, index=False)`）；
- 单元格是用 `str(program)` 而不是 `json.dumps(program)` 写入的；
- 文件带有 Excel 添加的字节顺序标记（BOM）；
- 校验子集时没有加上 `--partial`。

## 一段话看懂题目

每道题会在寄存器 `0..k-1` 中给出若干初始值、一份目标值列表以及数值上限 `value_limit`。一个程序由一连串指令 `[op, i, j, d]` 组成，表示“*寄存器 d ← 寄存器 i op 寄存器 j*”。共有 48 个寄存器。只要某个目标值出现在任意寄存器中，就立刻视为达成。当所有目标值都至少达成一次时，该题即告解出。得分是所有题目的指令总数，**越低越好**。挑战在于尽可能在各个目标之间共享中间值，用最少的算术步骤算出全部目标。

有三个细节很容易忽略：

- **两个源寄存器都在写入之前读取。** 因此 `d` 可以等于 `i` 或 `j`：`["+", 0, 0, 0]` 会原地把寄存器 0 翻倍。
- **允许 `i == j`。** `x / x = 1` 可以免费得到一个 1，而 `x + x` 可以直接翻倍。
- **初始寄存器可以被覆盖。** 初始值用完之后，它所在的寄存器就是一块普通的可用槽位。

## 检查项及原因

| 条款 | 检查内容 | 为什么重要 |
|---|---|---|
| 文件格式 | 表头必须严格为 `id,program`；每个题目 id 恰好出现一次；不能有未知 id；不能有多余列 | 哪怕缺少一行或重复一行，整个文件都会无效。 |
| 单元格大小 | 每个程序单元格 ≤ 131,072 个 UTF-8 字节（在 CSV 去除引号后计算） | 带缩进的 JSON 可能在触及 4,096 条指令上限之前就先超出这个字节限制；紧凑格式 JSON 则远低于上限。 |
| JSON | 单元格必须是指令组成的 JSON 数组，且最多 4,096 条指令 | |
| 指令 | 恰好 4 个元素；`op` ∈ `+ - * /`；`i, j, d` 为 `0..47` 范围内的整数 | |
| 源寄存器已定义 | 两个源寄存器中都必须已经有值 | 初始时只有寄存器 `0..len(start)-1` 有值，读取空寄存器属于非法操作。 |
| 结果为正数 | 每步运算结果都必须 ≥ 1 | `a - b` 要求 `a > b`，因此 `a - a = 0` 是非法的。 |
| 整除运算 | 仅当 `b` 能整除 `a` 时才允许使用 `/` | 不支持向下取整除法。 |
| 数值上限 | 每个结果都必须 ≤ `value_limit`，包括中间结果 | 先超出上限再除回来同样是非法的。 |
| 目标达成 | 目标值只要在任意时刻出现在任意寄存器中（包括初始状态），就算达成 | 之后覆盖掉该目标值不会取消其达成状态。本身就是初始值的目标不消耗任何指令。 |
| 指令计数 | 每一条指令都会计入得分，包括所有目标都达成之后的指令 | 末尾多余的无用指令会拉高分数，记得清理掉。 |

### 保守的额外检查

规则页面并未明确说明以下情况，但校验器仍会将其拒收，力求做到至少与正式评分器一样严格：

- 将寄存器索引写成 `true`/`false` 或 `1.0`。在 Python 中 `True == 1`，不严谨的校验代码会将其放行；
- 文件开头带有 UTF-8 字节顺序标记（BOM）；
- 包含 NUL 字节；
- 单独的 `\r` 换行符（Python 的 `csv.writer` 写出的 `\r\n` 是允许的）；
- 负数字面量，例如 `-0`。JSON 会把 `-0` 解析为整数 `0`，因此写成 `-0` 的寄存器编号会悄无声息地骗过简单校验器；
- 格式错误的 CSV 引号（文件以 `strict=True` 解析）；
- 空行。

校验器还会检查你传入的题目文件：对于正式计分集，题目 id 必须严格为 `scored_0001..scored_1000`，具有 48 个寄存器，且满足 `1 ≤ value_limit ≤ 10^18`。

加上 `--canonical` 还会额外要求每个单元格都是紧凑格式 JSON，即严格等于 `json.dumps(program, separators=(",", ":"))`。当你把多个工具生成的文件合并起来准备提交时，这很适合作为提交前的最后一道关卡。

**与 Kaggle 的一致度如何？** 就作者目前已提交的四份文件而言，本地算出的分数每次都与排行榜得分完全一致。这为常见情况提供了有力证据，但并不等同于证明了所有边界情况。

## 进阶命令

```bash
# 输出每道题的指令条数（仅在文件通过校验时写入）
python3 santa2026_verify.py sub.csv --puzzles puzzles.csv --per-puzzle lengths.csv

# 对比两份提交文件：统计更短／更长／相等的题数、双向差距最大的题目，
# 以及每题各取较短者时能拿到的最佳总分。--show N 用于指定列出多少条差异。
# 第二份文件始终在不启用 --canonical 的模式下检查。
python3 santa2026_verify.py mine.csv --puzzles puzzles.csv --compare other.csv --show 10

# 按寄存器逐步观看单个程序的运行过程（适合入门学习，也便于定位 ILLEGAL 步骤）
python3 santa2026_verify.py examples/toy_submission.csv --puzzles examples/toy_puzzles.csv --allow-non-scored --trace example_0001
# start [3]  targets left 4  limit 9
#     0  r1 = r0 / r0 = 3 / 3 = 1   <- target
#     1  r2 = r0 - r1 = 3 - 1 = 2   <- target
#     2  r3 = r0 + r2 = 3 + 2 = 5   <- target
#     3  r4 = r0 + r3 = 3 + 5 = 8   <- target
# done: 4 instructions, 0 targets not covered
# VALID puzzles=1 score=4
```

跟踪输出和错误信息中的步骤编号均从 0 开始；Data 页面中的表格是从 1 开始计数的。

退出状态码：

- `0`：有效；
- `1`：提交文件无效；
- `2`：使用或环境问题，例如题目文件不可读、找不到提交文件，或 `--per-puzzle` 指定的输出文件无法写入。

即便 `--compare` 报告另一份文件无效，退出状态码依然只反映主提交文件的校验结果。

在 Python 中调用：

```python
from santa2026_verify import load_puzzles, check_program, verify_file
P = load_puzzles("puzzles.csv")   # {id: {"start": [...], "targets": [...], "limit": int, "registers": int}}
ok, msg = check_program(P["scored_0001"], program)      # 单个程序（list 或 tuple）-> (bool, 原因)
ok, score, errors, lengths = verify_file("sub.csv", P)   # 整个文件；遇到格式错误的提交文件也不会抛出异常
# verify_file 默认与命令行一样，要求包含完整的计分题目集。
# 若用于练习题或子集，请传入 require_scored=False；此时该文件仅对该题目集有效。
```

`check_program` 很适合用来验证已完成的程序。它每次调用都会分配内存，因此不要把它放进搜索算法的内层循环中。

## 写出有效的提交文件

```python
import csv, json
with open("submission.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "program"])
    for pid, prog in programs.items():               # prog = [["+", 0, 0, 1], ...]
        w.writerow([pid, json.dumps(prog, separators=(",", ":"))])
# pandas: df.to_csv("submission.csv", index=False)  前提是 program 列已经是 json.dumps() 后的字符串
# R:      write.csv(df, "submission.csv", row.names = FALSE)
```

常见错误：

- 用 `str(program)` 写入（生成的是单引号，不是合法 JSON）；
- 忘了去掉 pandas 的索引列；
- 通过 Excel 保存，可能会加上 BOM 或把分隔符改成 `;`；
- 在 Windows 上配合 `csv.writer` 打开文件时忘了传 `newline=""`，从而产生 `\r\r\n` 换行符。

## 测试

`tests/test_santa2026_verify.py` 包含 66 个测试用例：

- 47 个必须被拒收的错误程序或错误文件；
- 14 个必须通过的合法边界用例；
- 5 项 Python API 契约检查。

`tests/test_cli.py` 会按真实用户的使用方式运行命令行，覆盖退出码、提示信息、`--partial`、`--compare`、`--trace`、`--per-puzzle`、`--canonical`、超长单元格与空单元格、Windows 换行符以及 cp1252 控制台。对于程序级用例，如果一个错误程序仅仅因为漏掉某个目标值而被拒收，测试同样会判失败——每个用例都必须确实触发它原本设计用来验证的那条规则。文件级用例只检查文件是否被拒收。测试还要求几个合法边界用例必须通过：Data 页面的示例、寄存器 47、恰好 4,096 条指令，以及运算结果恰好等于 `value_limit`。

```bash
python3 tests/test_santa2026_verify.py
python3 tests/test_cli.py
# 可选：以官方样例文件作为基准验证（其中最长的程序有 2873 条指令）：
ELF_PUZZLES=puzzles.csv ELF_SAMPLE=sample_submission.csv python3 tests/test_santa2026_verify.py
```

在 Windows 上请使用 `py`（或 `python`）代替 `python3`，并先设置环境变量：

- PowerShell：`$env:ELF_PUZZLES="puzzles.csv"; $env:ELF_SAMPLE="sample_submission.csv"; py tests\test_santa2026_verify.py`
- cmd：`set ELF_PUZZLES=puzzles.csv` 和 `set ELF_SAMPLE=sample_submission.csv`，然后运行 `py tests\test_santa2026_verify.py`

如果你发现某个文件被本校验器接受却被 Kaggle 拒收（或者相反），欢迎提交 issue。这类分歧正是本校验器最需要从中学习的案例。

## 许可证

MIT。详见 `LICENSE`。
