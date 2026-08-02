# Solar Design Agent — Equipment Datasheets & Knowledge Base

Place your equipment datasheets, manufacturer specification sheets, and manual PDFs/files in this directory so SolarBot and its multi-agent design engine automatically load and reference them for system designs.

## Folder Structure

- `datasheets/pv_modules/`: Place PV panel datasheets (.pdf, .txt, .docx, .json, .csv)
- `datasheets/inverters/`: Place inverter datasheets (.pdf, .txt, .docx, .json, .csv)
- `datasheets/batteries/`: Place BESS / battery datasheets & manuals (.pdf, .txt, .docx, .json, .csv)
- `datasheets/switchgear/`: Place cable, breaker, and protection switchgear spec sheets

## Supported File Formats
- `.pdf` (PDF spec sheets & product brochures)
- `.txt` / `.md` (Plain text / markdown technical specs)
- `.docx` (Microsoft Word datasheets)
- `.csv` / `.xlsx` (Excel component lists)
- `.json` (Structured component JSON specs)

All files placed in these folders are loaded at agent startup and referenced in stringing calculations, voltage limit verification, and BOQ generation.
