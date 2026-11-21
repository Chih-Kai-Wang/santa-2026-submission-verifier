# santa-2026-submission-verifier：適用於 Santa 2026 – The Elf Calculator 的嚴格本機驗證器

[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md)

`santa2026_verify.py` 是一個單一 Python 檔案（僅使用標準函式庫，需要 Python ≥ 3.8），用來依據公開規則檢查 Kaggle 競賽 *Santa 2026 – The Elf Calculator* 的提交檔案，並計算分數。這份 README 會帶你走過各項規則並說明每項檢查存在的原因，因此也適合作為這道題目的入門指南。

本專案不包含任何競賽資料檔案。唯一內附的競賽內容是取自 Data 頁面的小型範例，放在 `examples/` 中。你需要自行準備 `puzzles.csv`。

```bash
python3 santa2026_verify.py submission.csv --puzzles puzzles.csv
# VALID puzzles=1000 score=...        （結束碼 0） 或   ERROR ... / REJECTED errors=N   （結束碼 1）

# 任何其他題目檔案（如 practice_puzzles.csv 或你自己的測試題目）都需要加上 --allow-non-scored
python3 santa2026_verify.py my_practice_sub.csv --puzzles practice_puzzles.csv --allow-non-scored

# 只在解其中幾道題目嗎？--partial 只會檢查檔案中出現的題目 id
python3 santa2026_verify.py ten_puzzles.csv --puzzles puzzles.csv --partial
```

當檔案因常見原因被拒收時，程式會輸出一行 `HINT` 說明修正方式。常見原因包括：

- 多了 pandas 索引欄（請改用 `df.to_csv(path, index=False)`）；
- 儲存格是用 `str(program)` 而非 `json.dumps(program)` 寫入的；
- 檔案帶有 Excel 產生的位元組順序記號（BOM）；
- 驗證子集合時沒有加上 `--partial`。

## 一段話看懂題目

每道題目會在暫存器 `0..k-1` 中提供一組初始值、一份目標值清單以及上限 `value_limit`。一個程式是一連串指令 `[op, i, j, d]`，代表「*暫存器 d ← 暫存器 i op 暫存器 j*」。總共有 48 個暫存器。只要某個目標值出現在任一暫存器中，該目標就立刻視為達成。當所有目標值都至少達成過一次時，這道題目就算解開。最終分數是所有題目的指令總數，**越低越好**。挑戰的重點在於盡量共用各目標之間的中間值，用最少的算術步驟產出所有目標。

有三個細節很容易忽略：

- **兩個來源暫存器都會在寫入前先讀取。** 因此 `d` 可以等於 `i` 或 `j`：`["+", 0, 0, 0]` 會直接把暫存器 0 的值加倍並寫回原地。
- **允許 `i == j`。** `x / x = 1` 可以免費得到一個 1，而 `x + x` 則能直接加倍。
- **初始暫存器可以被覆寫。** 初始值用完之後，它所在的暫存器就只是一格普通的可用空間。

## 檢查項目與原因

| 條款 | 檢查內容 | 為什麼重要 |
|---|---|---|
| 檔案結構 | 標頭必須精確為 `id,program`；每個題目 id 恰好出現一次；不可有未知 id；不可有額外欄位 | 只要少一列或重複一列，整份檔案就會無效。 |
| 儲存格大小 | 每個程式儲存格 ≤ 131,072 個 UTF-8 位元組（在 CSV 去除引號後計算） | 帶縮排的 JSON 可能會在達到 4,096 條指令上限前就先超過這個大小限制；精簡格式（compact）JSON 則會遠低於上限。 |
| JSON | 儲存格必須是指令的 JSON 陣列，且最多 4,096 條指令 | |
| 指令 | 恰好 4 個元素；`op` ∈ `+ - * /`；`i, j, d` 為 `0..47` 之間的整數 | |
| 來源已定義 | 兩個來源暫存器都必須已有數值 | 一開始只有暫存器 `0..len(start)-1` 有值，讀取空暫存器屬於違法操作。 |
| 結果為正數 | 每個運算結果都必須 ≥ 1 | `a - b` 必須滿足 `a > b`，因此 `a - a = 0` 是違法的。 |
| 整除除法 | 只有在 `b` 能整除 `a` 時才允許使用 `/` | 沒有向下取整除法。 |
| 數值上限 | 每個結果都必須 ≤ `value_limit`，包含中間結果在內 | 先超過上限再除回來一樣是違法的。 |
| 目標達成 | 目標值只要在任意時刻出現在任一暫存器中（包含初始狀態），就算達成 | 之後覆寫掉該目標值也不會取消達成狀態。原本就是初始值的目標不需要任何步驟。 |
| 指令計數 | 每一條指令都會計入分數，包含所有目標達成之後的指令 | 尾端多餘的無用指令會增加分數，記得清理乾淨。 |

### 保守的額外檢查

規則頁面沒有明寫下列情況，但這個驗證器一律予以拒收，以確保它的嚴格程度至少不低於正式評分器：

- 以 `true`/`false` 或 `1.0` 表示暫存器索引。在 Python 中 `True == 1`，寫得不夠嚴謹的檢查程式會誤判為合法；
- 檔案開頭帶有 UTF-8 位元組順序記號（BOM）；
- 含有 NUL 位元組；
- 單獨的 `\r` 換行符號（Python 的 `csv.writer` 寫出的 `\r\n` 是沒問題的）；
- 負數數值字面值，例如 `-0`。JSON 會把 `-0` 解析成整數 `0`，因此如果把暫存器寫成 `-0`，簡單的檢查程式會悄悄放行；
- 格式錯誤的 CSV 引號（檔案會以 `strict=True` 解析）；
- 空白行。

驗證器也會檢查你指定的題目檔案：對於正式計分集，題目 id 必須精確為 `scored_0001..scored_1000`，具備 48 個暫存器，且 `1 ≤ value_limit ≤ 10^18`。

加上 `--canonical` 還會額外要求每個儲存格都是精簡格式 JSON，也就是完全符合 `json.dumps(program, separators=(",", ":"))`。當你把多個工具產出的檔案合併起來準備提交前，這很適合作為最後一道把關。

**與 Kaggle 的一致性如何？** 在作者目前提交的四份檔案中，本機計算的分數每次都與排行榜分數完全一致。這對常見情況是很有力的佐證，但不代表已證明涵蓋每一個邊界情況。

## 進階指令

```bash
# 輸出每道題目的指令數（僅在檔案驗證通過時寫入）
python3 santa2026_verify.py sub.csv --puzzles puzzles.csv --per-puzzle lengths.csv

# 比較兩份提交檔案：統計較短／較長／相等的題數、雙向差距最大的題目，
# 以及每題各取較短者能拿到的最佳總分。--show N 用來設定要列出幾筆差異。
# 第二份檔案一律在不啟用 --canonical 的條件下檢查。
python3 santa2026_verify.py mine.csv --puzzles puzzles.csv --compare other.csv --show 10

# 逐個暫存器觀察單一程式的執行過程（很適合用來學習，也方便找出 ILLEGAL 步驟）
python3 santa2026_verify.py examples/toy_submission.csv --puzzles examples/toy_puzzles.csv --allow-non-scored --trace example_0001
# start [3]  targets left 4  limit 9
#     0  r1 = r0 / r0 = 3 / 3 = 1   <- target
#     1  r2 = r0 - r1 = 3 - 1 = 2   <- target
#     2  r3 = r0 + r2 = 3 + 2 = 5   <- target
#     3  r4 = r0 + r3 = 3 + 5 = 8   <- target
# done: 4 instructions, 0 targets not covered
# VALID puzzles=1 score=4
```

追蹤輸出與錯誤訊息中的步驟編號從 0 開始；Data 頁面上的表格則是從 1 開始編號。

結束狀態碼：

- `0`：驗證通過；
- `1`：提交檔案無效；
- `2`：使用方式或環境問題，例如題目檔案無法讀取、找不到提交檔案，或無法寫入 `--per-puzzle` 指定的檔案。

即使 `--compare` 回報另一份檔案無效，結束狀態碼仍然只反映主要提交檔案的結果。

在 Python 中呼叫：

```python
from santa2026_verify import load_puzzles, check_program, verify_file
P = load_puzzles("puzzles.csv")   # {id: {"start": [...], "targets": [...], "limit": int, "registers": int}}
ok, msg = check_program(P["scored_0001"], program)      # 單一程式（list 或 tuple）-> (bool, 原因)
ok, score, errors, lengths = verify_file("sub.csv", P)   # 整份檔案；遇到格式錯誤的提交檔也不會拋出例外
# verify_file 預設與命令列一樣，要求包含完整的計分題目集。
# 若要檢查練習題或題目子集合，請傳入 require_scored=False；該檔案屆時僅對該題目集有效。
```

`check_program` 適合用來驗證已完成的程式。由於每次呼叫都會配置記憶體，請勿把它放進搜尋演算法的內層迴圈裡。

## 寫出有效的提交檔案

```python
import csv, json
with open("submission.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "program"])
    for pid, prog in programs.items():               # prog = [["+", 0, 0, 1], ...]
        w.writerow([pid, json.dumps(prog, separators=(",", ":"))])
# pandas: df.to_csv("submission.csv", index=False)  前提是 program 欄已轉成 json.dumps() 字串
# R:      write.csv(df, "submission.csv", row.names = FALSE)
```

常見錯誤：

- 用 `str(program)` 寫入（會產生單引號，不是合法 JSON）；
- 忘記關掉 pandas 的索引欄；
- 用 Excel 另存檔案，可能會加上 BOM 或把分隔符號改成 `;`；
- 在 Windows 上搭配 `csv.writer` 開啟檔案時忘了加 `newline=""`，導致產生 `\r\r\n` 換行符號。

## 測試

`tests/test_santa2026_verify.py` 包含 66 個測試案例：

- 47 個必須被拒收的錯誤程式或錯誤檔案；
- 14 個必須通過的合法邊界案例；
- 5 項 Python API 規格檢查。

`tests/test_cli.py` 會以實際使用者的方式執行命令列，測試結束狀態碼、提示訊息、`--partial`、`--compare`、`--trace`、`--per-puzzle`、`--canonical`、超大儲存格與空儲存格、Windows 換行符號以及 cp1252 主控台。在程式層級的測試案例中，如果某個錯誤程式只是因為漏掉目標值而被拒收，測試也會判定失敗——因此每個案例都必須確實觸發它原本設計要測試的那條規則。檔案層級的案例則只檢查檔案是否被拒收。測試也要求數個合法邊界案例必須通過：Data 頁面的範例、暫存器 47、剛好 4,096 條指令，以及運算結果恰好等於 `value_limit`。

```bash
python3 tests/test_santa2026_verify.py
python3 tests/test_cli.py
# 選用：以官方範例檔作為基準驗證（其中最長的程式有 2873 條指令）：
ELF_PUZZLES=puzzles.csv ELF_SAMPLE=sample_submission.csv python3 tests/test_santa2026_verify.py
```

在 Windows 上請用 `py`（或 `python`）取代 `python3`，並先設定環境變數：

- PowerShell：`$env:ELF_PUZZLES="puzzles.csv"; $env:ELF_SAMPLE="sample_submission.csv"; py tests\test_santa2026_verify.py`
- cmd：`set ELF_PUZZLES=puzzles.csv` 與 `set ELF_SAMPLE=sample_submission.csv`，接著執行 `py tests\test_santa2026_verify.py`

如果你發現有檔案被這個驗證器接受卻被 Kaggle 拒收（或相反），請開一個 issue。這類分歧正是這個驗證器最需要學習與修正的案例。

## 授權條款

MIT。詳見 `LICENSE`。
