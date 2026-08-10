"""
Datasheet Loader Module for Solar Design Agent.
Scans the local `datasheets/` repository folder for equipment spec sheets (.txt, .pdf, .docx, .json, .csv, .xlsx)
and formats them for SolarBot's engineering knowledge base.
"""
import os
import glob
from pathlib import Path
from typing import List, Dict, Any

DATASHEETS_DIR = Path(__file__).parent.parent / "datasheets"

def ensure_datasheet_dirs():
    """Creates the datasheets directory structure if it doesn't exist."""
    subdirs = ["pv_modules", "inverters", "batteries", "switchgear", "cables"]
    DATASHEETS_DIR.mkdir(exist_ok=True)
    for sd in subdirs:
        (DATASHEETS_DIR / sd).mkdir(exist_ok=True)

def load_all_datasheets() -> Dict[str, Any]:
    """
    Scans `datasheets/` directory and returns a dictionary of loaded datasheets.
    """
    ensure_datasheet_dirs()
    loaded_files = []
    summary_text = []

    patterns = ["**/*.txt", "**/*.md", "**/*.json", "**/*.csv", "**/*.pdf", "**/*.docx"]
    all_filepaths = []
    for pat in patterns:
        all_filepaths.extend(glob.glob(str(DATASHEETS_DIR / pat), recursive=True))

    for fp in sorted(all_filepaths):
        path_obj = Path(fp)
        filename = path_obj.name
        rel_path = path_obj.relative_to(DATASHEETS_DIR)
        category = path_obj.parent.name if path_obj.parent != DATASHEETS_DIR else "general"

        content = ""
        try:
            if fp.endswith(".json"):
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                with open(fp, "rb") as f:
                    file_bytes = f.read()
                from utils.file_parser import parse_uploaded_file
                content = parse_uploaded_file(file_bytes, filename)
        except Exception as e:
            content = f"[Error reading file {filename}: {e}]"

        if content:
            # Truncate per-file content to 1,200 characters to keep prompt token-efficient
            snippet = content.strip()[:1200]
            if len(content) > 1200:
                snippet += "\n...[truncated]"
            loaded_files.append({
                "filename": filename,
                "relative_path": str(rel_path),
                "category": category,
                "content": snippet
            })
            summary_text.append(f"=== DATASHEET: {filename} ({category}) ===\n{snippet}\n")

    kb_combined = "\n".join(summary_text) if summary_text else "No custom datasheets uploaded in datasheets/ folder yet."
    if len(kb_combined) > 6000:
        kb_combined = kb_combined[:6000] + "\n...[Additional datasheets truncated for token optimization]"

    return {
        "files_count": len(loaded_files),
        "files": loaded_files,
        "knowledge_base_text": kb_combined
    }
