# santa-2026-submission-verifier: Santa 2026 – The Elf Calculator를 위한 엄격한 로컬 검증기

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · **한국어** · [Español](README.es.md)

`santa2026_verify.py`는 단일 Python 파일(표준 라이브러리만 사용, Python ≥ 3.8)로, Kaggle 대회 *Santa 2026 – The Elf Calculator*의 제출 파일이 공개된 규칙을 지키는지 검사하고 점수를 계산합니다. 이 README는 규칙을 하나씩 살펴보며 각 검사가 왜 존재하는지 설명하므로, 문제 입문서로도 활용할 수 있습니다.

대회 데이터 파일은 포함되어 있지 않습니다. 여기 포함된 유일한 대회 콘텐츠는 Data 페이지의 작은 예제뿐이며, `examples/` 디렉터리에 들어 있습니다. `puzzles.csv` 파일은 직접 준비해야 합니다.

```bash
python3 santa2026_verify.py submission.csv --puzzles puzzles.csv
# VALID puzzles=1000 score=...        (종료 코드 0)   또는   ERROR ... / REJECTED errors=N   (종료 코드 1)

# 다른 퍼즐 파일(practice_puzzles.csv, 직접 만든 테스트 퍼즐 등)에는 --allow-non-scored가 필요합니다
python3 santa2026_verify.py my_practice_sub.csv --puzzles practice_puzzles.csv --allow-non-scored

# 일부 퍼즐만 작업 중인가요? --partial은 파일에 포함된 id만 검사합니다
python3 santa2026_verify.py ten_puzzles.csv --puzzles puzzles.csv --partial
```

흔한 이유로 파일이 거부되면 해결 방법을 알려주는 `HINT` 줄이 출력됩니다. 대표적인 원인은 다음과 같습니다.

- pandas 인덱스 열이 남아 있는 경우(`df.to_csv(path, index=False)` 사용)
- 셀을 `json.dumps(program)` 대신 `str(program)`으로 기록한 경우
- Excel이 추가한 바이트 순서 표식(BOM)이 들어 있는 경우
- 부분 집합을 검사하면서 `--partial` 옵션을 빠뜨린 경우

## 한 문단으로 보는 문제 개요

각 퍼즐에는 레지스터 `0..k-1`에 담긴 초깃값, 목표 값 목록, 그리고 상한 `value_limit`가 주어집니다. 프로그램은 `[op, i, j, d]` 형태의 명령어 목록이며, *레지스터 d ← 레지스터 i op 레지스터 j*를 뜻합니다. 레지스터는 총 48개입니다. 목표 값은 어느 레지스터에든 나타나는 순간 달성된 것으로 인정됩니다. 모든 목표 값을 최소 한 번 이상 달성하면 퍼즐이 풀립니다. 점수는 모든 퍼즐의 명령어 총합이며, **낮을수록 좋습니다**. 핵심은 목표 값들 사이에서 중간 값을 최대한 공유해 가장 적은 산술 단계로 모든 목표를 만들어 내는 것입니다.

놓치기 쉬운 세 가지 세부 사항이 있습니다.

- **쓰기 전에 두 소스 레지스터를 모두 먼저 읽습니다.** 따라서 `d`가 `i`나 `j`와 같아도 됩니다. 예를 들어 `["+", 0, 0, 0]`은 레지스터 0의 값을 그 자리에서 두 배로 만듭니다.
- **`i == j`가 허용됩니다.** `x / x = 1`로 손쉽게 1을 만들 수 있고, `x + x`로 값을 두 배로 늘릴 수 있습니다.
- **초기 레지스터도 덮어쓸 수 있습니다.** 초깃값을 다 쓰고 나면 해당 레지스터는 일반 빈 칸처럼 자유롭게 재사용할 수 있습니다.

## 검사 항목과 이유

| 항목 | 검사 내용 | 중요한 이유 |
|---|---|---|
| 파일 형식 | 헤더가 정확히 `id,program`이어야 함. 모든 퍼즐 id가 정확히 한 번씩 등장하고, 알 수 없는 id나 추가 열이 없어야 함 | 행이 하나라도 빠지거나 중복되면 파일 전체가 무효 처리됩니다. |
| 셀 크기 | 각 프로그램 셀이 131,072 UTF-8 바이트 이하(CSV 따옴표 해제 후 측정) | 들여쓰기가 들어간 JSON은 4,096개 명령어 제한에 닿기 전에 바이트 제한을 넘길 수 있습니다. 공백 없는 compact JSON은 한참 아래에 머뭅니다. |
| JSON | 셀이 명령어들로 이루어진 JSON 배열이며 4,096개 이하일 것 | |
| 명령어 | 정확히 4개의 원소. `op` ∈ `+ - * /`, `i, j, d`는 `0..47` 범위의 정수 | |
| 정의된 소스 | 두 소스 레지스터 모두 이미 값을 가지고 있어야 함 | 시작할 때는 `0..len(start)-1` 레지스터만 채워져 있습니다. 비어 있는 레지스터를 읽으면 규칙 위반입니다. |
| 양수 결과 | 모든 연산 결과는 1 이상이어야 함 | `a - b`는 `a > b`여야 하므로 `a - a = 0`은 허용되지 않습니다. |
| 나누어떨어지는 나눗셈 | `/`는 `b`가 `a`를 정확히 나눌 때만 허용됨 | 버림 나눗셈은 없습니다. |
| 값 상한 | 중간 값을 포함해 모든 연산 결과가 `value_limit` 이하여야 함 | 상한을 넘겼다가 다시 나누어 내려오는 것도 허용되지 않습니다. |
| 목표 달성 | 시작 상태를 포함해 어느 시점에든 어느 레지스터에 목표 값이 있으면 달성으로 인정됨 | 나중에 목표 값을 덮어쓰더라도 달성 상태는 취소되지 않습니다. 처음부터 초깃값에 들어 있는 목표는 비용이 0입니다. |
| 명령어 집계 | 모든 목표를 달성한 뒤의 명령어까지 포함해 모든 명령어가 점수에 합산됨 | 뒤에 남은 불필요한 명령어도 점수를 높이므로 정리해야 합니다. |

### 보수적인 추가 검사

규칙 페이지에 명시되어 있지는 않지만, 실제 채점기보다 최소한 같거나 더 엄격하게 검사하기 위해 검증기가 거부하는 항목들입니다.

- 레지스터 인덱스가 `true`/`false` 또는 `1.0`으로 적힌 경우. Python에서는 `True == 1`이라서 허술한 검사기라면 통과시켜 버립니다.
- 파일 맨 앞의 UTF-8 바이트 순서 표식(BOM)
- NUL 바이트
- 단독 `\r` 줄바꿈 문자(Python의 `csv.writer`가 쓰는 `\r\n`은 문제없습니다)
- `-0` 같은 음수 숫자 리터럴. JSON은 `-0`을 정수 `0`으로 파싱하므로 레지스터 번호에 `-0`을 써도 단순한 검사기는 조용히 통과시켜 버립니다.
- 잘못된 CSV 따옴표 처리(파일은 `strict=True`로 파싱합니다)
- 빈 줄

또한 지정한 퍼즐 파일 자체도 검사합니다. 채점용 세트는 정확히 `scored_0001..scored_1000`이어야 하며, 레지스터 48개와 `1 ≤ value_limit ≤ 10^18` 조건을 만족해야 합니다.

`--canonical` 옵션을 추가하면 모든 셀이 공백 없는 compact JSON, 즉 정확히 `json.dumps(program, separators=(",", ":"))` 형태인지까지 검사합니다. 여러 도구에서 만든 결과를 합쳐 제출하기 전에 최종 관문으로 쓰기 좋습니다.

**Kaggle 채점과 얼마나 일치하나요?** 작성자가 지금까지 제출한 네 개의 파일에서는 로컬 점수가 매번 리더보드 점수와 정확히 일치했습니다. 일반적인 경우에 대한 근거는 되지만, 모든 엣지 케이스를 증명하는 것은 아닙니다.

## 추가 명령어

```bash
# 퍼즐별 명령어 수 저장(파일이 유효할 때만 기록됨)
python3 santa2026_verify.py sub.csv --puzzles puzzles.csv --per-puzzle lengths.csv

# 두 제출 파일 비교: 더 짧은/긴/같은 퍼즐 개수, 양방향으로 차이가 가장 큰 퍼즐,
# 퍼즐마다 더 짧은 쪽을 골랐을 때의 최고 합산 점수 출력. --show N은 표시할 차이 개수를 지정.
# 두 번째 파일은 항상 --canonical 없이 검사됩니다.
python3 santa2026_verify.py mine.csv --puzzles puzzles.csv --compare other.csv --show 10

# 한 프로그램의 실행 과정을 레지스터별로 추적(문제 이해와 ILLEGAL 단계 찾기에 유용)
python3 santa2026_verify.py examples/toy_submission.csv --puzzles examples/toy_puzzles.csv --allow-non-scored --trace example_0001
# start [3]  targets left 4  limit 9
#     0  r1 = r0 / r0 = 3 / 3 = 1   <- target
#     1  r2 = r0 - r1 = 3 - 1 = 2   <- target
#     2  r3 = r0 + r2 = 3 + 2 = 5   <- target
#     3  r4 = r0 + r3 = 3 + 5 = 8   <- target
# done: 4 instructions, 0 targets not covered
# VALID puzzles=1 score=4
```

추적 출력과 오류 메시지의 단계 번호는 0부터 시작합니다. Data 페이지의 표는 1부터 셉니다.

종료 코드:

- `0`: 유효함
- `1`: 제출 파일이 유효하지 않음
- `2`: 사용상 오류(퍼즐 파일을 읽을 수 없거나, 제출 파일이 없거나, `--per-puzzle` 파일을 쓸 수 없는 경우 등)

`--compare`로 비교한 상대 파일이 유효하지 않다고 보고되더라도 종료 코드는 항상 메인 제출 파일의 결과만 반영합니다.

Python에서 사용하기:

```python
from santa2026_verify import load_puzzles, check_program, verify_file
P = load_puzzles("puzzles.csv")   # {id: {"start": [...], "targets": [...], "limit": int, "registers": int}}
ok, msg = check_program(P["scored_0001"], program)      # 프로그램 1개(list 또는 tuple) -> (bool, 사유)
ok, score, errors, lengths = verify_file("sub.csv", P)   # 파일 전체; 형식이 망가진 제출 파일에도 예외를 발생시키지 않음
# verify_file은 명령줄과 마찬가지로 기본적으로 전체 채점용 세트를 요구합니다.
# 연습용 퍼즐이나 부분 집합에는 require_scored=False를 전달하세요. 이 경우 해당 퍼즐 세트에 대해서만 유효합니다.
```

`check_program`은 완성된 프로그램을 검증할 때 적합합니다. 호출할 때마다 메모리를 할당하므로 탐색 알고리즘의 내부 루프에서는 사용하지 마세요.

## 유효한 제출 파일 작성하기

```python
import csv, json
with open("submission.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "program"])
    for pid, prog in programs.items():               # prog = [["+", 0, 0, 1], ...]
        w.writerow([pid, json.dumps(prog, separators=(",", ":"))])
# pandas: df.to_csv("submission.csv", index=False)  program 열은 이미 json.dumps()로 변환된 문자열이어야 함
# R:      write.csv(df, "submission.csv", row.names = FALSE)
```

자주 하는 실수:

- `str(program)`으로 기록하는 경우(작은따옴표가 들어가 유효한 JSON이 아님)
- pandas 인덱스를 그대로 남기는 경우
- Excel로 저장해 BOM이 붙거나 구분자가 `;`로 바뀌는 경우
- Windows에서 `csv.writer`와 함께 파일을 열 때 `newline=""`을 생략해 `\r\r\n` 줄바꿈이 생기는 경우

## 테스트

`tests/test_santa2026_verify.py`에는 66개의 테스트 케이스가 있습니다.

- 거부되어야 하는 잘못된 프로그램 또는 파일 47개
- 통과해야 하는 유효한 엣지 케이스 14개
- Python API 규약 검사 5개

`tests/test_cli.py`는 실제 사용자처럼 명령줄을 실행하며 종료 코드, 힌트, `--partial`, `--compare`, `--trace`, `--per-puzzle`, `--canonical`, 크기 초과 셀과 빈 셀, Windows 줄바꿈, cp1252 콘솔을 검증합니다. 프로그램 단위 케이스에서는 잘못된 프로그램이 단순히 목표 값 누락 때문에 거부되기만 하면 테스트가 실패하도록 되어 있어, 각 케이스가 의도한 규칙을 정확히 위반해야 합니다. 파일 단위 케이스는 파일이 거부되는지만 확인합니다. 또한 Data 페이지의 예제, 레지스터 47, 정확히 4,096개의 명령어, `value_limit`와 정확히 같은 연산 결과 등 몇 가지 유효한 엣지 케이스가 반드시 통과하도록 요구합니다.

```bash
python3 tests/test_santa2026_verify.py
python3 tests/test_cli.py
# 선택 사항: 공식 샘플 제출 파일 기준 검증(가장 긴 프로그램은 2873개 명령어):
ELF_PUZZLES=puzzles.csv ELF_SAMPLE=sample_submission.csv python3 tests/test_santa2026_verify.py
```

Windows에서는 `python3` 대신 `py`(또는 `python`)를 사용하고 환경 변수를 먼저 설정하세요.

- PowerShell: `$env:ELF_PUZZLES="puzzles.csv"; $env:ELF_SAMPLE="sample_submission.csv"; py tests\test_santa2026_verify.py`
- cmd: `set ELF_PUZZLES=puzzles.csv`와 `set ELF_SAMPLE=sample_submission.csv` 실행 후 `py tests\test_santa2026_verify.py`

이 검증기에서는 통과했는데 Kaggle에서 거부된 파일, 또는 반대의 경우를 발견하면 이슈를 열어 주세요. 그런 불일치야말로 이 검증기가 보완해 나가야 할 가장 중요한 사례입니다.

## 라이선스

MIT. 자세한 내용은 `LICENSE`를 참고하세요.
