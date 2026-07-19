"""
Site Visit Report Analyzer.
Extracts structured solar design data from uploaded files using GitHub Models (gpt-4o)
or Google Gemini (gemini-1.5-flash/2.5-flash/2.0-flash).
"""
import os
import json
import re
import time
from typing import Optional
from google.genai import types

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

FALLBACK_MODELS = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

EXTRACTION_PROMPT = """
You are analyzing a site visit report for a solar PV installation.
Extract all available information and return a JSON object with these fields:

{
  "client_name": "",
  "site_location": "",
  "gps_coordinates": "",
  "site_description": "",
  "grid_available": null,
  "grid_voltage": "",
  "grid_phases": "",
  "existing_equipment": [],
  "roof_type": "",
  "roof_area_sqm": null,
  "roof_orientation": "",
  "shading_issues": "",
  "ground_mount_available": false,
  "loads": [
    {
      "name": "Load name",
      "quantity": 1,
      "wattage": 0,
      "hours_per_day": 0,
      "days_per_week": 7
    }
  ],
  "total_connected_load_kw": null,
  "daily_energy_kwh": null,
  "system_type_recommended": "off-grid|hybrid|grid-tied|unknown",
  "special_notes": "",
  "images_description": ""
}

If any field is not mentioned in the report, use null or empty string.
Return ONLY the JSON object, no markdown, no explanation.
"""


def _try_openai_extraction(prompt: str) -> Optional[dict]:
    """Try extracting data via Featherless AI or GitHub Models if configured."""
    featherless_token = os.getenv("FEATHERLESS_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")
    if not HAS_OPENAI or (not featherless_token and not github_token):
        return None

    try:
        import httpx
        if featherless_token:
            client = OpenAI(
                base_url="https://api.featherless.ai/v1",
                api_key=featherless_token,
                http_client=httpx.Client()
            )
            model = os.getenv("FEATHERLESS_MODEL", "deepseek-ai/DeepSeek-V3.1-Terminus")
        else:
            client = OpenAI(
                base_url=os.getenv("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference"),
                api_key=github_token,
                http_client=httpx.Client()
            )
            model = os.getenv("GITHUB_MODEL", "gpt-4o")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a specialized solar engineering data extraction AI."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=3000
        )
        return _parse_json_response(response.choices[0].message.content)
    except Exception as e:
        print(f"[OpenAI/Featherless extraction fallback]: {e}")
        return None


def _generate_with_fallback(client, contents, initial_model: str, temperature: float = 0.1):
    models_to_try = [initial_model] + [m for m in FALLBACK_MODELS if m != initial_model]
    for model_name in models_to_try:
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(temperature=temperature),
            )
        except Exception as e:
            print(f"[Gemini {model_name} extraction error]: {e}")
            time.sleep(1.0)
            continue
    return None


def extract_from_text(text_content: str, client, model_id: str) -> dict:
    """Extract site data from plain text using Featherless, GitHub Models, or Gemini."""
    prompt = f"{EXTRACTION_PROMPT}\n\nREPORT CONTENT:\n{text_content[:15000]}"
    
    # 1. Try Featherless AI or GitHub Models
    openai_res = _try_openai_extraction(prompt)
    if openai_res:
        return openai_res

    # 2. Try Gemini fallback
    if client and model_id:
        response = _generate_with_fallback(client, prompt, initial_model=model_id)
        if response and hasattr(response, "text"):
            return _parse_json_response(response.text)
    return {}


def extract_from_image(image_bytes: bytes, mime_type: str, client, model_id: str) -> dict:
    """Extract site data from an image using Gemini Vision with automatic rate-limit fallback."""
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        EXTRACTION_PROMPT,
    ]
    response = _generate_with_fallback(client, contents, initial_model=model_id)
    return _parse_json_response(response.text)


def _parse_json_response(text: str) -> dict:
    """Parses JSON from AI response, strips markdown fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {}


def format_extracted_data(data: dict) -> str:
    """Returns a markdown summary of extracted site data for chat display."""
    if not data:
        return "⚠️ Could not extract structured data from the report."

    lines = ["## 📋 Site Visit Report — Extracted Data", ""]

    def add(label, key, suffix=""):
        val = data.get(key)
        if val is not None and val != "" and val != []:
            lines.append(f"- **{label}:** {val}{suffix}")

    add("Client Name", "client_name")
    add("Location", "site_location")
    add("GPS Coordinates", "gps_coordinates")
    add("Site Description", "site_description")
    add("Grid Available", "grid_available")
    add("Grid Voltage", "grid_voltage")
    add("Grid Phases", "grid_phases")
    add("Roof Type", "roof_type")
    add("Roof Area", "roof_area_sqm", " m²")
    add("Roof Orientation", "roof_orientation")
    add("Shading Issues", "shading_issues")
    add("Recommended System Type", "system_type_recommended")
    add("Special Notes", "special_notes")

    loads = data.get("loads", [])
    if loads:
        lines.append("")
        lines.append("### ⚡ Extracted Loads")
        lines.append("| Appliance / Load | Qty | Wattage | Hours/Day |")
        lines.append("|---|:---:|:---:|:---:|")
        for l in loads:
            name = l.get("name", "Load")
            qty  = l.get("quantity", 1)
            w    = l.get("wattage", 0)
            h    = l.get("hours_per_day", 0)
            lines.append(f"| {name} | {qty} | {w}W | {h}h |")

    eq = data.get("existing_equipment", [])
    if eq:
        lines.append("")
        lines.append("### ⚙️ Existing Equipment")
        for item in eq:
            lines.append(f"- {item}")

    return "\n".join(lines)
