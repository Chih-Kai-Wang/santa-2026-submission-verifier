# santa-2026-submission-verifier：Santa 2026 – The Elf Calculator 向けの厳格なローカル検証ツール

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · **日本語** · [한국어](README.ko.md) · [Español](README.es.md)

`santa2026_verify.py` は単一の Python ファイル（標準ライブラリのみ使用、Python ≥ 3.8）で、Kaggle コンペティション *Santa 2026 – The Elf Calculator* の提出ファイルが公開ルールに適合しているか検証し、スコアを計算します。この README ではルールをひと通り確認しながら各チェックが存在する理由も説明しているため、問題そのものの入門ガイドとしても活用できます。

コンペティションのデータファイルは含まれていません。同梱しているのは Data ページに掲載されている小さな例題（`examples/` 内）のみです。`puzzles.csv` はご自身でご用意ください。

```bash
python3 santa2026_verify.py submission.csv --puzzles puzzles.csv
# VALID puzzles=1000 score=...        （終了コード 0） または   ERROR ... / REJECTED errors=N   （終了コード 1）

# その他のパズルファイル（practice_puzzles.csv や自作テストパズルなど）には --allow-non-scored が必要
python3 santa2026_verify.py my_practice_sub.csv --puzzles practice_puzzles.csv --allow-non-scored

# 一部のパズルだけに取り組んでいますか？ --partial はファイルに含まれる id だけを検証します
python3 santa2026_verify.py ten_puzzles.csv --puzzles puzzles.csv --partial
```

よくある原因でファイルが却下された場合、修正方法を示す `HINT` 行が出力されます。よくある原因は次のとおりです。

- pandas のインデックス列が残っている（`df.to_csv(path, index=False)` を使用してください）
- セルが `json.dumps(program)` ではなく `str(program)` で書き出されている
- Excel が付けたバイトオーダーマーク（BOM）が含まれている
- 部分集合のファイルを `--partial` なしでチェックしている

## 問題の概要をひとまとめに

各パズルでは、レジスタ `0..k-1` に入れられた初期値、ターゲット値のリスト、そして上限値 `value_limit` が与えられます。プログラムは `[op, i, j, d]` という命令のリストで、*レジスタ d ← レジスタ i op レジスタ j* を意味します。レジスタは 48 個あります。ターゲットはいずれかのレジスタに現れた瞬間に達成とみなされます。すべてのターゲットを少なくとも一度達成すればパズルはクリアです。スコアは全パズルを通じた命令の総数で、**小さいほど高評価**になります。できる限りターゲット間で中間値を共有しながら、いかに少ない算術ステップですべてのターゲットを作り出せるかが勝負です。

見落としやすいポイントが 3 つあります。

- **書き込みの前に 2 つの参照元レジスタが両方読み込まれます。** そのため `d` は `i` や `j` と同じでも構いません。たとえば `["+", 0, 0, 0]` はレジスタ 0 をその場で 2 倍にします。
- **`i == j` も許可されています。** `x / x = 1` で手軽に 1 を作れますし、`x + x` で 2 倍にできます。
- **初期値が入ったレジスタも上書きできます。** 初期値を使い終えたら、そのレジスタは通常の空きスロットとして自由に再利用できます。

## チェック内容とその理由

| 項目 | チェック内容 | 重要な理由 |
|---|---|---|
| ファイル形式 | ヘッダーが厳密に `id,program` であること。すべてのパズル id がちょうど 1 回ずつ含まれ、未知の id や余分な列がないこと | 1 行でも欠けたり重複したりすると、ファイル全体が無効になります。 |
| セルサイズ | 各プログラムセルが 131,072 UTF-8 バイト以下であること（CSV の引用符解除後に計測） | インデント付き JSON は、4,096 命令の上限に達する前にこのバイト制限を超えることがあります。コンパクトな JSON なら十分に余裕があります。 |
| JSON | セルが命令の JSON 配列であり、命令数が 4,096 以下であること | |
| 命令 | 要素数がちょうど 4 つであること。`op` ∈ `+ - * /`、`i, j, d` は `0..47` の整数であること | |
| 定義済みの参照元 | 2 つの参照元レジスタの両方にすでに値が入っていること | 開始時点で値が入っているのは `0..len(start)-1` のみです。空のレジスタを読むのは違反です。 |
| 正の演算結果 | すべての演算結果が 1 以上であること | `a - b` では `a > b` が必要なので、`a - a = 0` は違反になります。 |
| 割り切れる除算 | `/` は `b` が `a` をちょうど割り切るときのみ許可される | 切り捨て除算はありません。 |
| 値の上限 | 中間値を含め、すべての演算結果が `value_limit` 以下であること | 一度上限を超えてから割って戻すことも違反です。 |
| ターゲット達成 | 開始時を含め、いずれかの時点でいずれかのレジスタにターゲットが存在すれば達成とみなされる | 後からターゲットを上書きしても、達成状態は取り消されません。最初から初期値として入っているターゲットはコスト 0 です。 |
| 命令カウント | すべてのターゲットを達成した後の命令も含め、すべての命令がカウントされる | 末尾の不要な命令もスコアを悪化させるので取り除きましょう。 |

### 念のための追加チェック

ルールページには明記されていないケースですが、公式スコアラーと同等以上の厳格さを保つため、本検証ツールでは以下も却下します。

- レジスタ番号として `true`/`false` や `1.0` が使われている場合。Python では `True == 1` となるため、甘いチェッカーだと通してしまいます。
- ファイル先頭の UTF-8 バイトオーダーマーク（BOM）
- NUL バイト
- 単独の `\r` 改行コード（Python の `csv.writer` が出力する `\r\n` は問題ありません）
- `-0` のような負の数値リテラル。JSON は `-0` を整数の `0` としてパースするため、レジスタ番号に `-0` と書いても単純なチェッカーは素通りさせてしまいます。
- 不正な CSV クォート（`strict=True` でパースします）
- 空行

また、指定されたパズルファイル自体も検証します。スコア対象のセットでは、id が厳密に `scored_0001..scored_1000` であり、レジスタ数が 48、かつ `1 ≤ value_limit ≤ 10^18` である必要があります。

`--canonical` を付けると、すべてのセルがコンパクトな JSON、すなわち厳密に `json.dumps(program, separators=(",", ":"))` 形式であることも要求します。複数ツールの出力を統合した後の提出前チェックとして便利です。

**Kaggle の採点とどこまで一致するか？** 作者自身がこれまでに提出した 4 つのファイルでは、ローカルスコアとリーダーボードスコアが毎回完全に一致しています。一般的なケースについての裏付けにはなりますが、あらゆるエッジケースを証明するものではありません。

## 追加コマンド

```bash
# パズルごとの命令数を出力（ファイルが有効な場合のみ書き出されます）
python3 santa2026_verify.py sub.csv --puzzles puzzles.csv --per-puzzle lengths.csv

# 2 つの提出ファイルを比較：短い／長い／同じパズルの件数、双方で差が最も大きいパズル、
# パズルごとに短い方を採用した場合の理論ベストスコアを表示。--show N で表示する差分件数を指定。
# 2 つ目のファイルは常に --canonical なしで検証されます。
python3 santa2026_verify.py mine.csv --puzzles puzzles.csv --compare other.csv --show 10

# 1 つのプログラムの実行をレジスタ単位で追跡（仕組みの理解や ILLEGAL ステップの特定に便利）
python3 santa2026_verify.py examples/toy_submission.csv --puzzles examples/toy_puzzles.csv --allow-non-scored --trace example_0001
# start [3]  targets left 4  limit 9
#     0  r1 = r0 / r0 = 3 / 3 = 1   <- target
#     1  r2 = r0 - r1 = 3 - 1 = 2   <- target
#     2  r3 = r0 + r2 = 3 + 2 = 5   <- target
#     3  r4 = r0 + r3 = 3 + 5 = 8   <- target
# done: 4 instructions, 0 targets not covered
# VALID puzzles=1 score=4
```

トレース出力やエラーメッセージ中のステップ番号は 0 始まりです。Data ページの表は 1 から数えています。

終了ステータス：

- `0`：有効
- `1`：提出ファイルが無効
- `2`：使用上の問題（パズルファイルが読めない、提出ファイルが存在しない、`--per-puzzle` の出力先に書き込めないなど）

`--compare` で比較対象のファイルが無効と報告された場合でも、終了ステータスにはメインの提出ファイルの結果のみが反映されます。

Python からの利用：

```python
from santa2026_verify import load_puzzles, check_program, verify_file
P = load_puzzles("puzzles.csv")   # {id: {"start": [...], "targets": [...], "limit": int, "registers": int}}
ok, msg = check_program(P["scored_0001"], program)      # 1 つのプログラム（list または tuple）-> (bool, 理由)
ok, score, errors, lengths = verify_file("sub.csv", P)   # ファイル全体；壊れた提出ファイルでも例外を送出しない
# verify_file はコマンドラインと同様、デフォルトでスコア対象の全セットを要求します。
# 練習用パズルや部分集合の場合は require_scored=False を渡してください。その場合、そのパズルセットに対してのみ有効になります。
```

`check_program` は完成したプログラムを検証するのに適しています。呼び出しごとにメモリを確保するため、探索の内側ループでは使わないでください。

## 有効な提出ファイルの書き方

```python
import csv, json
with open("submission.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "program"])
    for pid, prog in programs.items():               # prog = [["+", 0, 0, 1], ...]
        w.writerow([pid, json.dumps(prog, separators=(",", ":"))])
# pandas: df.to_csv("submission.csv", index=False)  program 列はあらかじめ json.dumps() 済みの文字列にしておくこと
# R:      write.csv(df, "submission.csv", row.names = FALSE)
```

よくあるミス：

- `str(program)` で書き出してしまう（シングルクォートになり、JSON として不正）
- pandas のインデックスを付けたままにしてしまう
- Excel を通して保存してしまい、BOM が付いたり区切り文字が `;` に変わったりする
- Windows で `csv.writer` を使う際に `newline=""` を指定せず開き、`\r\r\n` という改行になってしまう

## テスト

`tests/test_santa2026_verify.py` には 66 件のテストケースがあります。

- 却下されるべき不正なプログラム・ファイル：47 件
- 通過すべき有効なエッジケース：14 件
- Python API 仕様の確認：5 件

`tests/test_cli.py` は実際のユーザーと同様にコマンドラインを実行し、終了コード、ヒント、`--partial`、`--compare`、`--trace`、`--per-puzzle`、`--canonical`、サイズ超過セルと空セル、Windows の改行コード、cp1252 コンソールを検証します。プログラム単位のケースでは、不正なプログラムが単にターゲット不足を理由に却下されただけではテストが失敗するようになっているため、各ケースは想定どおりのルール違反を確実に起こす必要があります。ファイル単位のケースではファイルが却下されることだけを確認します。また、Data ページの例題、レジスタ 47、ちょうど 4,096 命令、`value_limit` とちょうど等しい演算結果など、いくつかの有効なエッジケースが通過することも検証します。

```bash
python3 tests/test_santa2026_verify.py
python3 tests/test_cli.py
# 任意：公式サンプル提出ファイルを使った基準テスト（最長プログラムは 2873 命令）：
ELF_PUZZLES=puzzles.csv ELF_SAMPLE=sample_submission.csv python3 tests/test_santa2026_verify.py
```

Windows では `python3` の代わりに `py`（または `python`）を使い、先に環境変数を設定してください。

- PowerShell：`$env:ELF_PUZZLES="puzzles.csv"; $env:ELF_SAMPLE="sample_submission.csv"; py tests\test_santa2026_verify.py`
- cmd：`set ELF_PUZZLES=puzzles.csv` と `set ELF_SAMPLE=sample_submission.csv` を実行してから `py tests\test_santa2026_verify.py`

この検証ツールでは通るのに Kaggle では却下されたファイル、あるいはその逆を見つけた場合は、ぜひ issue を立ててください。そうした食い違いこそが、このツールを改善していくための最も大切なケースです。

## ライセンス

MIT。詳細は `LICENSE` をご覧ください。
