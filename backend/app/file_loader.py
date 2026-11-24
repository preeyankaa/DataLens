"""
app/file_loader.py

Reads the files people really have, not only perfect CSVs:

  * CSV / TSV / TXT with a comma, semicolon, tab or pipe separator
  * UTF-8, UTF-8 with BOM, UTF-16 (Excel "Unicode text") and Windows-1252
  * Excel .xlsx / .xlsm (the sheet with the most data is used)
  * title rows above the real column headers
  * empty rows, empty columns, blank or repeated column names

load_dataframe() returns (dataframe, info). info["notes"] is a list of plain
sentences describing anything that was fixed automatically, so nothing
happens silently.
"""

import csv
import io
import re
from collections import Counter
from itertools import islice

import pandas as pd

CSV_EXTENSIONS = (".csv", ".tsv", ".txt")
EXCEL_EXTENSIONS = (".xlsx", ".xlsm")
SUPPORTED_EXTENSIONS = CSV_EXTENSIONS + EXCEL_EXTENSIONS

_DELIMITERS = [",", ";", "\t", "|"]
_DELIMITER_NAMES = {";": "semicolon", "\t": "tab", "|": "pipe"}
_HEADER_SCAN_ROWS = 20


class LoadError(ValueError):
    """A problem with the uploaded file that can be shown to the user."""


# --------------------------------------------------
# helpers
# --------------------------------------------------

def _decode(contents):
    """Return (text, encoding_label, note_or_None)."""
    if contents.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return contents.decode("utf-16"), "utf-16", None
        except UnicodeDecodeError:
            pass

    if b"\x00" in contents[:4096]:
        raise LoadError(
            "This file looks like a binary file, not a CSV. "
            "Please upload a CSV or an Excel (.xlsx) file."
        )

    try:
        return contents.decode("utf-8-sig"), "utf-8", None
    except UnicodeDecodeError:
        pass

    try:
        return (
            contents.decode("cp1252"),
            "windows-1252",
            "The file was not UTF-8, so it was read as Windows-1252. "
            "Check that names with accents look right.",
        )
    except UnicodeDecodeError:
        return (
            contents.decode("latin-1"),
            "latin-1",
            "The file encoding was unclear, so it was read as Latin-1. "
            "Check that names with accents look right.",
        )


def _detect_delimiter(text):
    lines = [line for line in text.splitlines()[:30] if line.strip()]
    if not lines:
        raise LoadError("The file is empty.")

    best, best_score = ",", -1.0

    for delimiter in _DELIMITERS:
        counts = [line.count(delimiter) for line in lines]
        mode, frequency = Counter(counts).most_common(1)[0]
        if mode == 0:
            continue
        score = frequency / len(counts) + 0.001 * min(mode, 50)
        if score > best_score:
            best, best_score = delimiter, score

    return best


def _header_row(rows):
    """Index of the first row that looks like the real header."""
    counts = [
        sum(1 for cell in row if str(cell).strip() not in ("", "nan", "None"))
        for row in rows
    ]
    if not counts or max(counts) == 0:
        return 0

    needed = max(2, 0.6 * max(counts))
    for index, count in enumerate(counts):
        if count >= needed:
            return index
    return 0


def _clean_columns(columns, notes):
    """Readable, unique column names. Returns (names, auto_named_set)."""
    names, auto, seen = [], set(), {}
    renamed_blank = renamed_repeat = trimmed = 0

    raw_names = {str(c) for c in columns}

    for position, raw in enumerate(columns, start=1):
        original = "" if raw is None else str(raw)
        name = re.sub(r"\s+", " ", original).strip()

        # pandas already renamed repeated headers to "a.1", "a.2"
        mangled = re.match(r"^(.*)\.(\d+)$", name)
        if mangled and mangled.group(1) in raw_names:
            name = f"{mangled.group(1)}_{int(mangled.group(2)) + 1}"
            seen[mangled.group(1)] = max(
                seen.get(mangled.group(1), 0), int(mangled.group(2)) + 1
            )
            renamed_repeat += 1
            names.append(name)
            continue

        if name != original and name:
            trimmed += 1

        if not name or name.lower().startswith("unnamed:") or name.lower() == "nan":
            name = f"Column_{position}"
            auto.add(name)
            renamed_blank += 1

        base = name
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            name = f"{base}_{seen[base]}"
            renamed_repeat += 1

        names.append(name)

    if trimmed:
        notes.append(f"Extra spaces were removed from {trimmed} column name(s).")
    if renamed_blank:
        notes.append(f"{renamed_blank} column(s) had no name and were called Column_N.")
    if renamed_repeat:
        notes.append(f"{renamed_repeat} repeated column name(s) were numbered (_2, _3).")

    return names, auto


def _tidy(df, notes):
    df = df.copy()
    df.columns, auto = _clean_columns(list(df.columns), notes)

    empty_auto = [c for c in df.columns if c in auto and df[c].isna().all()]
    if empty_auto:
        df = df.drop(columns=empty_auto)
        notes.append(f"Removed {len(empty_auto)} completely empty column(s).")

    before = len(df)
    df = df.dropna(how="all")
    removed_rows = before - len(df)
    if removed_rows:
        notes.append(f"Removed {removed_rows} completely empty row(s).")

    return df.reset_index(drop=True)


# --------------------------------------------------
# readers
# --------------------------------------------------

def _load_csv(contents):
    notes = []
    text, encoding, encoding_note = _decode(contents)
    if encoding_note:
        notes.append(encoding_note)

    delimiter = _detect_delimiter(text)
    if delimiter != ",":
        notes.append(f"This is a {_DELIMITER_NAMES[delimiter]}-separated file. It was read correctly.")

    preview = list(
        islice(csv.reader(io.StringIO(text), delimiter=delimiter), _HEADER_SCAN_ROWS)
    )
    skip = _header_row(preview)
    if skip:
        notes.append(f"Skipped {skip} title row(s) above the column headers.")

    def read(**extra):
        return pd.read_csv(
            io.StringIO(text), sep=delimiter, skiprows=skip, **extra
        )

    try:
        df = read()
    except pd.errors.EmptyDataError:
        raise LoadError("The file has no readable data or column headers.")
    except pd.errors.ParserError:
        try:
            df = read(on_bad_lines="skip")
            notes.append("Some lines had the wrong number of columns and were skipped.")
        except Exception:
            raise LoadError(
                "Could not read this file. Check that every row has the same "
                "number of columns."
            )

    return df, {
        "format": "csv",
        "encoding": encoding,
        "delimiter": delimiter,
    }, notes


def _load_excel(contents):
    notes = []

    try:
        sheets = pd.read_excel(
            io.BytesIO(contents), sheet_name=None, header=None, engine="openpyxl"
        )
    except ImportError:
        raise LoadError(
            "Excel support is not installed on the server. Run: pip install openpyxl"
        )
    except Exception:
        raise LoadError(
            "Could not read this Excel file. Make sure it is a valid .xlsx "
            "file and is not password protected."
        )

    sizes = {name: int(frame.notna().sum().sum()) for name, frame in sheets.items()}
    if not sizes or max(sizes.values()) == 0:
        raise LoadError("The Excel file has no data.")

    sheet = max(sizes, key=sizes.get)
    others = [name for name in sheets if name != sheet and sizes[name] > 0]
    if others:
        notes.append(
            f"Read the sheet '{sheet}' (the one with the most data). "
            f"Other sheets were ignored: {', '.join(map(str, others))}."
        )

    raw = (
        sheets[sheet].dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    )

    preview = raw.head(_HEADER_SCAN_ROWS).fillna("").values.tolist()
    skip = _header_row(preview)
    if skip:
        notes.append(f"Skipped {skip} title row(s) above the column headers.")

    header = raw.iloc[skip].tolist()
    body = raw.iloc[skip + 1:].reset_index(drop=True)
    body.columns = ["" if pd.isna(h) else h for h in header]
    body = body.infer_objects()

    return body, {"format": "excel", "sheet": str(sheet)}, notes


# --------------------------------------------------
# public API
# --------------------------------------------------

def load_dataframe(contents, filename):
    """
    Parse an uploaded file.
    Returns (dataframe, info) where info["notes"] lists automatic fixes.
    """
    name = (filename or "").lower()

    if name.endswith(CSV_EXTENSIONS):
        df, info, notes = _load_csv(contents)
    elif name.endswith(EXCEL_EXTENSIONS):
        df, info, notes = _load_excel(contents)
    else:
        raise LoadError(
            "Please upload a CSV or Excel (.xlsx) file. Older .xls files "
            "can be re-saved as .xlsx."
        )

    df = _tidy(df, notes)

    if len(df.columns) == 0:
        raise LoadError("The file does not contain any columns.")
    if len(df) == 0:
        raise LoadError("The file has column headers but no data rows.")

    info["notes"] = notes
    info["rows"] = int(len(df))
    info["columns"] = int(len(df.columns))
    return df, info