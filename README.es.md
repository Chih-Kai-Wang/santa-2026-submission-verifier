# santa-2026-submission-verifier: un verificador local estricto para Santa 2026 – The Elf Calculator

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Español**

`santa2026_verify.py` es un único archivo de Python (solo biblioteca estándar, Python ≥ 3.8) que comprueba un archivo de envío para la competición de Kaggle *Santa 2026 – The Elf Calculator* frente a las reglas publicadas y calcula su puntuación. Este README recorre las reglas y explica por qué existe cada comprobación, por lo que también sirve como introducción al problema.

No se incluye ningún archivo de datos de la competición. El único contenido de la competición aquí es el pequeño ejemplo ilustrativo de la página Data, en `examples/`. Necesitas tu propia copia de `puzzles.csv`.

```bash
python3 santa2026_verify.py submission.csv --puzzles puzzles.csv
# VALID puzzles=1000 score=...        (código de salida 0)   o   ERROR ... / REJECTED errors=N   (código de salida 1)

# cualquier otro archivo de puzles (practice_puzzles.csv, tus propios puzles de prueba) necesita --allow-non-scored
python3 santa2026_verify.py my_practice_sub.csv --puzzles practice_puzzles.csv --allow-non-scored

# ¿solo estás trabajando en unos pocos puzles? --partial comprueba únicamente los ids presentes en el archivo
python3 santa2026_verify.py ten_puzzles.csv --puzzles puzzles.csv --partial
```

Cuando un archivo se rechaza por un motivo habitual, una línea `HINT` explica cómo solucionarlo. Los motivos más comunes son:

- una columna de índice de pandas (usa `df.to_csv(path, index=False)`);
- celdas escritas con `str(program)` en lugar de `json.dumps(program)`;
- una marca de orden de bytes (BOM) añadida por Excel;
- comprobar un subconjunto sin `--partial`.

## El problema en un párrafo

Cada puzle proporciona algunos valores iniciales en los registros `0..k-1`, una lista de valores objetivo y un límite `value_limit`. Un programa es una lista de instrucciones `[op, i, j, d]`, que significa *registro d ← registro i op registro j*. Hay 48 registros. Un objetivo cuenta como cubierto en cuanto aparece en cualquier registro. Un puzle queda resuelto cuando todos los objetivos se han cubierto al menos una vez. La puntuación es el número total de instrucciones en todos los puzles, y **cuanto más baja, mejor**. El reto consiste en producir todos los objetivos con el menor número posible de pasos aritméticos, compartiendo valores intermedios entre objetivos siempre que puedas.

Tres detalles fáciles de pasar por alto:

- **Ambos registros fuente se leen antes de escribir.** Por eso `d` puede ser igual a `i` o a `j`: `["+", 0, 0, 0]` duplica el registro 0 en el mismo sitio.
- **Se permite `i == j`.** `x / x = 1` te da un 1 gratis, y `x + x` duplica el valor.
- **Los registros iniciales se pueden sobrescribir.** Una vez que has usado un valor inicial, su registro pasa a ser un hueco libre más.

## Qué se comprueba y por qué

| Cláusula | Comprobación | Por qué importa |
|---|---|---|
| Formato del archivo | Encabezado exactamente `id,program`; cada id de puzle exactamente una vez; sin ids desconocidos; sin columnas extra | Una sola fila faltante o duplicada invalida todo el archivo. |
| Tamaño de celda | Cada celda de programa ≤ 131,072 bytes UTF-8 (medidos tras quitar las comillas del CSV) | Un JSON con sangría puede superar este límite antes de alcanzar el límite de 4,096 instrucciones. El JSON compacto queda muy por debajo. |
| JSON | La celda es un arreglo JSON de instrucciones, con ≤ 4,096 de ellas | |
| Instrucción | Exactamente 4 elementos; `op` ∈ `+ - * /`; `i, j, d` enteros en `0..47` | |
| Fuentes definidas | Ambos registros fuente deben contener ya un valor | Solo los registros `0..len(start)-1` comienzan con valores. Leer un registro vacío es ilegal. |
| Resultados positivos | Cada resultado debe ser ≥ 1 | `a - b` requiere `a > b`, así que `a - a = 0` es ilegal. |
| División exacta | `/` solo se permite cuando `b` divide exactamente a `a` | No hay división entera con redondeo hacia abajo. |
| Límite de valor | Cada resultado debe ser ≤ `value_limit`, incluidos los valores intermedios | Pasarse del límite y volver a bajar dividiendo sigue siendo ilegal. |
| Cobertura | Un objetivo queda cubierto si está en cualquier registro en cualquier momento, incluido el inicio | Sobrescribir un objetivo más adelante no anula su cobertura. Un objetivo que ya es un valor inicial no cuesta nada. |
| Conteo | Todas las instrucciones cuentan, incluidas las posteriores a haber cubierto todos los objetivos | Las instrucciones muertas al final empeoran la puntuación, así que elimínalas. |

### Controles adicionales conservadores

Las páginas de reglas no especifican estos casos de forma explícita. El verificador los rechaza de todos modos, con la intención de ser al menos tan estricto como el evaluador oficial:

- índices de registro dados como `true`/`false` o `1.0`. En Python `True == 1`, así que un verificador descuidado los aceptaría;
- una marca de orden de bytes (BOM) UTF-8 al principio del archivo;
- bytes NUL;
- finales de línea con solo `\r` (el `\r\n` que escribe `csv.writer` de Python es válido);
- literales numéricos negativos como `-0`. JSON interpreta `-0` como el entero `0`, así que un registro escrito como `-0` pasaría desapercibido en un verificador ingenuo;
- comillas CSV mal formadas (el archivo se analiza con `strict=True`);
- líneas en blanco.

También valida el archivo de puzles que le indiques: para el conjunto puntuable debe ser exactamente `scored_0001..scored_1000`, con 48 registros y `1 ≤ value_limit ≤ 10^18`.

`--canonical` exige además que todas las celdas sean JSON compacto, es decir, exactamente `json.dumps(program, separators=(",", ":"))`. Resulta útil como filtro previo al envío cuando combinas archivos de varias herramientas.

**¿Qué tan bien coincide con Kaggle?** En los envíos del propio autor hasta ahora (cuatro archivos), la puntuación local ha coincidido siempre con la de la tabla de clasificación. Es evidencia para los casos habituales, no una prueba para todos los casos límite.

## Comandos adicionales

```bash
# conteo de instrucciones por puzle (solo se escribe cuando el archivo es válido)
python3 santa2026_verify.py sub.csv --puzzles puzzles.csv --per-puzzle lengths.csv

# comparar dos envíos: cuántos puzles son más cortos/largos/iguales, las mayores diferencias en ambos sentidos
# y qué puntuación daría quedarse con lo mejor de ambos por puzle. --show N define cuántas diferencias se muestran.
# El segundo archivo siempre se comprueba sin --canonical.
python3 santa2026_verify.py mine.csv --puzzles puzzles.csv --compare other.csv --show 10

# ver cómo se ejecuta un programa registro por registro (útil para aprender y para encontrar un paso ILLEGAL)
python3 santa2026_verify.py examples/toy_submission.csv --puzzles examples/toy_puzzles.csv --allow-non-scored --trace example_0001
# start [3]  targets left 4  limit 9
#     0  r1 = r0 / r0 = 3 / 3 = 1   <- target
#     1  r2 = r0 - r1 = 3 - 1 = 2   <- target
#     2  r3 = r0 + r2 = 3 + 2 = 5   <- target
#     3  r4 = r0 + r3 = 3 + 5 = 8   <- target
# done: 4 instructions, 0 targets not covered
# VALID puzzles=1 score=4
```

Los números de paso en las trazas y mensajes de error empiezan en 0. La tabla de la página Data cuenta desde 1.

Código de salida:

- `0`: válido;
- `1`: el envío no es válido;
- `2`: problema de uso, como un archivo de puzles ilegible, un archivo de envío inexistente o un archivo `--per-puzzle` que no se pudo escribir.

El código de salida refleja únicamente el envío principal, incluso cuando `--compare` indica que el otro archivo no es válido.

Desde Python:

```python
from santa2026_verify import load_puzzles, check_program, verify_file
P = load_puzzles("puzzles.csv")   # {id: {"start": [...], "targets": [...], "limit": int, "registers": int}}
ok, msg = check_program(P["scored_0001"], program)      # un programa (listas o tuplas) -> (bool, motivo)
ok, score, errors, lengths = verify_file("sub.csv", P)   # archivo completo; nunca lanza excepciones por un envío mal formado
# verify_file exige por defecto el conjunto puntuable completo, igual que la línea de comandos.
# Para puzles de práctica o un subconjunto pasa require_scored=False; el archivo solo será válido para ese conjunto de puzles.
```

`check_program` sirve bien para comprobar programas terminados. Realiza asignaciones de memoria en cada llamada, así que no lo uses en el bucle interno de una búsqueda.

## Cómo escribir un envío válido

```python
import csv, json
with open("submission.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "program"])
    for pid, prog in programs.items():               # prog = [["+", 0, 0, 1], ...]
        w.writerow([pid, json.dumps(prog, separators=(",", ":"))])
# pandas: df.to_csv("submission.csv", index=False)  con la columna program ya convertida a cadenas con json.dumps()
# R:      write.csv(df, "submission.csv", row.names = FALSE)
```

Errores frecuentes:

- escribir `str(program)` (comillas simples, no es JSON);
- dejar activado el índice de pandas;
- guardar pasando por Excel, que puede añadir un BOM o cambiar el separador a `;`;
- en Windows, abrir el archivo sin `newline=""` al usar `csv.writer`, lo que produce saltos de línea `\r\r\n`.

## Pruebas

`tests/test_santa2026_verify.py` tiene 66 casos:

- 47 programas o archivos rotos que deben rechazarse;
- 14 casos límite válidos que deben pasar;
- 5 comprobaciones del contrato de la API de Python.

`tests/test_cli.py` ejecuta la línea de comandos tal como lo haría un usuario: códigos de salida, pistas, `--partial`, `--compare`, `--trace`, `--per-puzzle`, `--canonical`, celdas demasiado grandes y vacías, saltos de línea de Windows y una consola cp1252. En los casos a nivel de programa, la prueba también falla si un programa inválido solo se rechaza porque falta un objetivo, de modo que cada caso tiene que infringir exactamente la regla para la que se escribió. Los casos a nivel de archivo comprueban únicamente que el archivo sea rechazado. Las pruebas también exigen que pasen varios casos límite válidos: el ejemplo ilustrativo de la página Data, el registro 47, exactamente 4,096 instrucciones y un resultado igual a `value_limit`.

```bash
python3 tests/test_santa2026_verify.py
python3 tests/test_cli.py
# comprobación opcional frente a la muestra oficial (su programa más largo tiene 2873 instrucciones):
ELF_PUZZLES=puzzles.csv ELF_SAMPLE=sample_submission.csv python3 tests/test_santa2026_verify.py
```

En Windows usa `py` (o `python`) en lugar de `python3`. Define primero las variables:

- PowerShell: `$env:ELF_PUZZLES="puzzles.csv"; $env:ELF_SAMPLE="sample_submission.csv"; py tests\test_santa2026_verify.py`
- cmd: `set ELF_PUZZLES=puzzles.csv` y `set ELF_SAMPLE=sample_submission.csv`, y luego `py tests\test_santa2026_verify.py`

Si encuentras un archivo que este verificador acepta y Kaggle rechaza, o al revés, abre un issue por favor. Esas discrepancias son exactamente los casos de los que debe aprender.

## Licencia

MIT. Consulta `LICENSE`.
