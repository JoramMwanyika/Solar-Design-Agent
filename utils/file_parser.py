"""
File parser — extracts text content from uploaded files.
Supports PDF, DOCX, Excel, plain text, and passes images to Gemini Vision.
"""
import io
from pathlib import Path


def parse_uploaded_file(file_bytes: bytes, filename: str) -> str:
    """
    Parses an uploaded file and returns its text content.
    Returns empty string for image files (handled separately by Gemini Vision).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return _parse_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return _parse_docx(file_bytes)
    elif ext in (".xlsx", ".xls"):
        return _parse_excel(file_bytes)
    elif ext in (".txt", ".csv"):
        return file_bytes.decode("utf-8", errors="ignore")
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return ""  # Images handled by Gemini Vision
    else:
        # Try UTF-8 decode as fallback
        try:
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return ""


def _parse_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
                # Also extract tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        text_parts.append(" | ".join(str(c or "") for c in row))
        return "\n".join(text_parts)
    except ImportError:
        return ""
    except Exception as e:
        return f"[PDF parse error: {e}]"


def _parse_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)
        # Tables
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(parts)
    except ImportError:
        return ""
    except Exception as e:
        return f"[DOCX parse error: {e}]"


def _parse_excel(file_bytes: bytes) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        parts = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            parts.append(f"=== Sheet: {sheet_name} ===")
            for row in ws.iter_rows(values_only=True):
                row_text = " | ".join(str(c) if c is not None else "" for c in row)
                if row_text.strip(" |"):
                    parts.append(row_text)
        return "\n".join(parts)
    except ImportError:
        return ""
    except Exception as e:
        return f"[Excel parse error: {e}]"


def get_mime_type(filename: str) -> str:
    """Returns MIME type from filename extension."""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".csv": "text/csv",
    }
    return mime_map.get(ext, "application/octet-stream")


def extract_loads_from_dataframe(df_raw) -> tuple[list[dict], bool]:
    """
    Intelligently extracts load items from any uploaded CSV/Excel DataFrame.
    Automatically handles both:
      1) Standard Appliance Schedules (summing items)
      2) Logged Meter Time-Series Data (peak interval & daily averages)
    Returns: (loads_list, is_time_series_flag)
    """
    import pandas as pd
    import re

    if df_raw is None or df_raw.empty:
        return [], False

    df = df_raw.copy()

    # Step 1: Check if top rows are metadata/header rows (common in Fluke/meter logs)
    def looks_like_header(row_vals):
        words = set()
        for v in row_vals:
            if pd.notna(v):
                for w in str(v).lower().replace("(", " ").replace(")", " ").replace("[", " ").replace("]", " ").replace("-", " ").replace("_", " ").split():
                    words.add(w)
        power_hits = sum(1 for kw in ("watt", "watts", "wattage", "active", "apparent", "power", "kw", "kva") if kw in words)
        if power_hits >= 1:
            return True
        general_hits = sum(1 for kw in ("name", "appliance", "item", "description", "timestamp", "time", "date", "interval", "load", "demand", "quantity", "qty", "hours") if kw in words)
        return general_hits >= 2

    # If current headers don't look like a valid table header, scan first 20 rows for the true header
    if not looks_like_header(df.columns):
        for idx in range(min(20, len(df))):
            row_vals = df.iloc[idx].values
            if looks_like_header(row_vals):
                df.columns = [str(v).strip() if pd.notna(v) else f"col_{i}" for i, v in enumerate(row_vals)]
                df = df.iloc[idx + 1:].reset_index(drop=True)
                break

    # Clean column names for mapping
    col_map = {str(c).lower().strip(): c for c in df.columns}

    def find_col(*candidates):
        # 1. Try exact matches first
        for cand in candidates:
            if cand in col_map:
                return col_map[cand]
        # 2. Try substring matches (word boundary or clear descriptive match)
        for cand in candidates:
            for c_low, c_orig in col_map.items():
                if cand in c_low and not c_low.startswith("unnamed"):
                    return c_orig
        return None

    # Candidate columns
    col_name = find_col("name", "appliance", "item", "description", "timestamp", "time", "date", "interval", "device", "load", "equipment")
    col_p = find_col("wattage", "active power", "active_power", "active", "real power", "real_power", "p (kw)", "p (w)", "p(kw)", "p(w)", "p [kw]", "p [w]", "p_kw", "kw", "watt", "watts", "w", "ptotal", "power")
    col_s = find_col("apparent wattage", "apparent_wattage", "apparent power", "apparent_power", "apparent", "s (kva)", "s (va)", "s(kva)", "s(va)", "s [kva]", "s [va]", "s_kva", "kva", "va", "stotal")
    col_qty = find_col("quantity", "qty", "count", "num", "units")
    col_hrs = find_col("hours_per_day", "hours", "hrs", "duration", "runtime", "operating hours", "h/day")

    # If neither P nor S was found by keywords, fallback to first numeric columns
    if not col_p and not col_s:
        numeric_cols = []
        for c in df.columns:
            try:
                s_num = pd.to_numeric(df[c].astype(str).str.replace(",", "").str.replace("$", "").str.strip(), errors="coerce")
                if s_num.notna().sum() >= max(1, len(df) * 0.4):
                    numeric_cols.append(c)
            except Exception:
                pass
        if len(numeric_cols) >= 1:
            col_p = numeric_cols[0]
        if len(numeric_cols) >= 2 and col_s is None:
            col_s = numeric_cols[1]

    # Detect if this is a Time-Series log vs. Appliance Schedule
    is_time_series = False
    if col_name and any(kw in str(col_name).lower() for kw in ("time", "date", "timestamp", "interval")):
        is_time_series = True
    elif len(df) >= 15 and not col_qty and not col_hrs:
        is_time_series = True

    def parse_number(val):
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            return float(val) if val == val else None
        s = str(val).replace(",", "").replace("$", "").strip()
        m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
        if m:
            return float(m.group(0))
        return None

    csv_loads = []
    for idx, row in df.iterrows():
        p_val = 0.0
        if col_p is not None:
            raw_p = parse_number(row.get(col_p))
            if raw_p is not None and raw_p > 0:
                if col_p and ("kw" in str(col_p).lower() or (is_time_series and raw_p < 150.0 and "w" not in str(col_p).lower())):
                    p_val = raw_p * 1000.0
                else:
                    p_val = raw_p

        s_val = None
        if col_s is not None:
            raw_s = parse_number(row.get(col_s))
            if raw_s is not None and raw_s > 0:
                if col_s and ("kva" in str(col_s).lower() or (raw_s < 150.0 and "va" not in str(col_s).lower())):
                    s_val = raw_s * 1000.0
                else:
                    s_val = raw_s

        if p_val > 0 or (s_val is not None and s_val > 0):
            item_name = str(row[col_name]).strip() if (col_name and pd.notna(row.get(col_name))) else (f"Interval {idx+1}" if is_time_series else f"Item {idx+1}")
            qty_val = parse_number(row.get(col_qty)) if col_qty else 1
            hrs_val = parse_number(row.get(col_hrs)) if col_hrs else 1.0

            csv_loads.append({
                "name": item_name,
                "wattage": p_val if p_val > 0 else (s_val * 0.85 if s_val else 0),
                "quantity": int(qty_val) if (qty_val is not None and qty_val > 0) else 1,
                "hours_per_day": float(hrs_val) if (hrs_val is not None and hrs_val > 0) else 1.0,
                "apparent_wattage": s_val,
                "is_time_series": is_time_series
            })

    return csv_loads, is_time_series
