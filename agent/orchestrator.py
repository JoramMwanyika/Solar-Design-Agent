"""
Main Agent Orchestrator — manages AI conversation, intent routing,
file processing, and response generation.
Supports Dual-Brain Architecture:
1. GitHub Models (gpt-4o) via GITHUB_TOKEN (Primary when configured)
2. Google Gemini (gemini-1.5-flash/2.5-flash) via GEMINI_API_KEY (Automatic fallback & alternative)
"""
import os
import json
import re
import time
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from agent.system_sizer import size_system, LoadItem, format_sizing_summary, SizingResult
from agent.boq_generator import generate_boq_excel, boq_to_markdown_table, generate_boq
from agent.report_analyzer import extract_from_text, extract_from_image, format_extracted_data
from utils.file_parser import parse_uploaded_file

load_dotenv(override=True)

# Load prompts
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    try:
        return (_PROMPTS_DIR / name).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


SYSTEM_PROMPT = _load_prompt("system_prompt.txt")
SIZING_PROMPT = _load_prompt("sizing_prompt.txt")
BOQ_PROMPT    = _load_prompt("boq_prompt.txt")

DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
FALLBACK_GEMINI_MODELS = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]


class SolarAgent:
    """
    Main agent class. One instance per Streamlit session.
    Supports GitHub Models (gpt-4o) + Google GenAI with stateful chat & resilience.
    """

    def __init__(self):
        self.version = "3.1"
        self.featherless_token = os.getenv("FEATHERLESS_API_KEY")
        self.featherless_model = os.getenv("FEATHERLESS_MODEL", "deepseek-ai/DeepSeek-V3.1-Terminus")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_model = os.getenv("GITHUB_MODEL", "gpt-4o")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        # Determine active brain: Featherless > GitHub Models > Gemini
        if self.featherless_token and HAS_OPENAI:
            self.active_engine = "featherless"
            import httpx
            self.openai_client = OpenAI(
                base_url="https://api.featherless.ai/v1",
                api_key=self.featherless_token,
                http_client=httpx.Client()
            )
            self.active_model = self.featherless_model
            self.gpt_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        elif self.github_token and HAS_OPENAI:
            self.active_engine = "github-gpt-4o"
            import httpx
            self.openai_client = OpenAI(
                base_url=os.getenv("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference"),
                api_key=self.github_token,
                http_client=httpx.Client()
            )
            self.active_model = self.github_model
            self.gpt_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        else:
            self.active_engine = "gemini"
            self.openai_client = None
            self.active_model = None
            self.gpt_history = []

        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
            self.current_gemini_model = DEFAULT_GEMINI_MODEL
            self._chat_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
            )
            self.gemini_chat = self._create_gemini_chat(self.current_gemini_model)
        else:
            self.gemini_client = None
            self.gemini_chat = None

        if not self.openai_client and not self.gemini_client:
            raise EnvironmentError("Neither FEATHERLESS_API_KEY, GITHUB_TOKEN, nor GEMINI_API_KEY is set.")

        # State
        self.system_type: str = "off-grid"
        self.last_sizing_result: Optional[SizingResult] = None
        self.last_boq_items: list[dict] = []
        self.last_boq_excel: Optional[bytes] = None
        self.extracted_site_data: Optional[dict] = None

    def _create_gemini_chat(self, model_id: str, history: Optional[list] = None):
        if not self.gemini_client:
            return None
        try:
            return self.gemini_client.chats.create(
                model=model_id,
                config=self._chat_config,
                history=history or [],
            )
        except Exception:
            return self.gemini_client.chats.create(
                model=model_id,
                config=self._chat_config,
            )

    def _send_chat_message_safe(self, message: str) -> str:
        """Sends chat message prioritizing Featherless AI / GitHub Models, falling back to Gemini."""
        # 1. Try Featherless AI or GitHub Models via OpenAI client
        if self.active_engine in ("featherless", "github-gpt-4o") and self.openai_client:
            self.gpt_history.append({"role": "user", "content": message})
            try:
                resp = self.openai_client.chat.completions.create(
                    model=self.active_model,
                    messages=self.gpt_history,
                    temperature=0.4,
                    max_tokens=2500
                )
                text = resp.choices[0].message.content
                self.gpt_history.append({"role": "assistant", "content": text})
                return text
            except Exception as e:
                print(f"[{self.active_engine} ({self.active_model}) chat error, falling back]: {e}")
                if self.gpt_history and self.gpt_history[-1]["role"] == "user":
                    self.gpt_history.pop()

        # 2. Fallback to Gemini
        if not self.gemini_chat:
            return f"⚠️ **AI Engine Error:** {self.active_engine} failed and no Gemini backup key is available."

        models_to_try = [self.current_gemini_model] + [m for m in FALLBACK_GEMINI_MODELS if m != self.current_gemini_model]
        for idx, model_name in enumerate(models_to_try):
            try:
                if model_name != self.current_gemini_model:
                    try:
                        history = self.gemini_chat.get_history()
                    except Exception:
                        history = []
                    self.current_gemini_model = model_name
                    self.gemini_chat = self._create_gemini_chat(model_name, history)

                response = self.gemini_chat.send_message(message)
                return response.text
            except Exception as e:
                print(f"[Gemini {model_name} error in chat]: {e}")
                time.sleep(1.0)
                continue

        return (
            "⚠️ **AI API Notice:** All AI model APIs are currently rate-limited or offline. "
            "All local calculations, system sizing, and Excel BOQ generation still work 100% offline!"
        )

    def _generate_content_safe(self, contents: str, temperature: float = 0.1) -> str:
        """Generates content prioritizing Featherless AI / GitHub Models, falling back to Gemini."""
        if self.active_engine in ("featherless", "github-gpt-4o") and self.openai_client:
            try:
                resp = self.openai_client.chat.completions.create(
                    model=self.active_model,
                    messages=[
                        {"role": "system", "content": "You are a specialized solar engineering extraction assistant."},
                        {"role": "user", "content": contents}
                    ],
                    temperature=temperature,
                    max_tokens=3000
                )
                return resp.choices[0].message.content
            except Exception as e:
                print(f"[{self.active_engine} generate_content error]: {e}")

        if not self.gemini_client:
            return ""

        models_to_try = [self.current_gemini_model] + [m for m in FALLBACK_GEMINI_MODELS if m != self.current_gemini_model]
        for idx, model_name in enumerate(models_to_try):
            try:
                resp = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(temperature=temperature),
                )
                return resp.text
            except Exception as e:
                print(f"[Gemini {model_name} error in generate_content]: {e}")
                time.sleep(1.0)
                continue
        return ""

    def set_system_type(self, system_type: str):
        self.system_type = system_type

    # ─────────────────────────────────────────
    # File Processing
    # ─────────────────────────────────────────

    def process_uploaded_file(self, file_bytes: bytes, filename: str, mime_type: str) -> str:
        """Processes an uploaded file, extracts site data, and returns a chat message."""
        text_content = parse_uploaded_file(file_bytes, filename)

        if text_content:
            client_to_use = self.gemini_client if self.gemini_client else self.github_client
            model_to_use = self.current_gemini_model if self.gemini_client else self.github_model
            self.extracted_site_data = extract_from_text(
                text_content, client_to_use, model_to_use
            )
        elif mime_type.startswith("image/") and self.gemini_client:
            self.extracted_site_data = extract_from_image(
                file_bytes, mime_type, self.gemini_client, self.current_gemini_model
            )
        else:
            return (
                f"⚠️ Could not parse `{filename}`. "
                f"Supported: PDF, DOCX, Excel, CSV, PNG, JPG."
            )

        summary = format_extracted_data(self.extracted_site_data)

        context_msg = (
            f"A site visit report has been uploaded and analyzed. "
            f"Here is the extracted data:\n\n{summary}\n\n"
            f"Please acknowledge this data and ask the user if they want to proceed "
            f"with system sizing, or if there is any data to correct or add."
        )
        return self._send_chat_message_safe(context_msg)

    # ─────────────────────────────────────────
    # Chat
    # ─────────────────────────────────────────

    def chat_message(self, user_message: str) -> tuple[str, Optional[bytes], Optional[list]]:
        """Sends a message to the agent and returns (response_text, boq_excel, boq_items)."""
        if self._is_boq_request(user_message) and self.last_sizing_result:
            return self._generate_boq_response()

        if self._is_sizing_request(user_message) or self._has_load_data(user_message):
            structured_prompt = (
                f"{SIZING_PROMPT}\n\n"
                f"User message: {user_message}\n\n"
                f"Extracted site data (if any): "
                f"{json.dumps(self.extracted_site_data or {})}\n\n"
                f"System type selected: {self.system_type}\n\n"
                f"If you have enough data, extract load items and return the sizing "
                f"JSON output format, then a natural language explanation. "
                f"If you need more information, ask the user."
            )
            text = self._send_chat_message_safe(structured_prompt)

            sizing_data = self._extract_json(text)
            if sizing_data and "panel_qty" in sizing_data:
                loads = self._parse_loads_from_site_data()
                if loads:
                    result = size_system(
                        system_type=self.system_type,
                        loads=loads,
                        location=sizing_data.get("location", "East Africa"),
                        days_of_autonomy=sizing_data.get("days_of_autonomy", 2.0),
                        panel_wp=sizing_data.get("panel_wp", 625),
                    )
                    self.last_sizing_result = result
                    summary_md = format_sizing_summary(result)
                    return (
                        summary_md
                        + "\n\n---\n*Type **'generate BOQ'** to create the Bill of Quantities.*",
                        None,
                        None,
                    )

            return text, None, None

        text = self._send_chat_message_safe(user_message)
        return text, None, None

    # ─────────────────────────────────────────
    # Direct Sizing (from Quick Form or CSV)
    # ─────────────────────────────────────────

    @staticmethod
    def pd_notna_check(val) -> bool:
        if val is None or val == "" or val != val:
            return False
        return True

    def run_sizing(
        self,
        loads: list[dict],
        location: str = "East Africa",
        days_of_autonomy: float = 2.0,
        dod: float = 0.8,
        system_voltage_dc: int = 48,
        battery_voltage: float = 51.2,
        battery_ah_rating: int = 280,
        panel_wp: int = 625,
        mppt_rating: int = 60,
    ) -> tuple[str, SizingResult]:
        """Direct sizing call (used from UI quick form or CSV load upload)."""
        load_items = [
            LoadItem(
                name=str(l.get("name", "Load")),
                wattage=float(l.get("wattage", 0)),
                quantity=int(l.get("quantity", 1)),
                hours_per_day=float(l.get("hours_per_day", 1)),
                apparent_wattage=float(l["apparent_wattage"]) if l.get("apparent_wattage") is not None and self.pd_notna_check(l.get("apparent_wattage")) else None,
                power_factor=float(l.get("power_factor", 0.85)) if l.get("power_factor") is not None and self.pd_notna_check(l.get("power_factor")) else 0.85,
                is_time_series=bool(l.get("is_time_series", False)),
            )
            for l in loads
            if float(l.get("wattage", 0)) > 0 or (l.get("apparent_wattage") is not None and self.pd_notna_check(l.get("apparent_wattage")) and float(l["apparent_wattage"]) > 0)
        ]
        result = size_system(
            system_type=self.system_type,
            loads=load_items,
            location=location or "East Africa",
            days_of_autonomy=float(days_of_autonomy),
            dod=float(dod),
            system_voltage_dc=int(system_voltage_dc),
            battery_voltage=float(battery_voltage),
            panel_wp=int(panel_wp),
        )
        self.last_sizing_result = result
        md = format_sizing_summary(result)

        try:
            self._send_chat_message_safe(
                f"System sizing has been completed via the Quick Form/CSV Upload. Results:\n{md}\n"
                f"The user can now type 'generate BOQ' to create the Bill of Quantities."
            )
        except Exception:
            pass

        return md, result

    # ─────────────────────────────────────────
    # BOQ Generation
    # ─────────────────────────────────────────

    def generate_boq(
        self,
        project_name: str = "Solar PV System",
        client_name: str = "",
        prepared_by: str = "",
        location: str = "",
    ) -> tuple[str, bytes, list[dict]]:
        """Generate BOQ from last sizing result."""
        if not self.last_sizing_result:
            return "❌ Please complete system sizing before generating a BOQ.", b"", []

        result = self.last_sizing_result
        sizing_dict = result.to_dict()

        boq_items = []
        try:
            boq_prompt = (
                f"{BOQ_PROMPT}\n\n"
                f"Based on these sizing results, generate a complete BOQ JSON array:\n"
                f"{json.dumps(sizing_dict, indent=2)}\n\n"
                f"System type: {result.system_type}\n"
                f"Return ONLY the JSON array."
            )
            raw_text = self._generate_content_safe(boq_prompt)
            boq_items = self._extract_json_array(raw_text)
        except Exception:
            boq_items = []

        if not boq_items:
            boq_items = self._template_boq(result)

        self.last_boq_items = boq_items

        excel_bytes = generate_boq_excel(
            boq_items=boq_items,
            project_name=project_name,
            system_type=result.system_type,
            location=location or result.location,
            client_name=client_name,
            prepared_by=prepared_by,
            sizing_summary=sizing_dict,
        )
        self.last_boq_excel = excel_bytes

        md_table = boq_to_markdown_table(boq_items)
        return md_table, excel_bytes, boq_items

    # ─────────────────────────────────────────
    # Private Helpers
    # ─────────────────────────────────────────

    def _generate_boq_response(self) -> tuple[str, Optional[bytes], Optional[list]]:
        md, excel, items = self.generate_boq()
        return (
            f"## 📋 Bill of Quantities\n\n{md}\n\n"
            f"✅ BOQ generated! Click the **Download BOQ (Excel)** button below.",
            excel,
            items,
        )

    def _is_boq_request(self, msg: str) -> bool:
        keywords = ["boq", "bill of quantities", "generate boq", "create boq",
                    "bill of material", "bom", "procurement list"]
        return any(k in msg.lower() for k in keywords)

    def _is_sizing_request(self, msg: str) -> bool:
        keywords = ["size", "sizing", "calculate", "design", "system for",
                    "how many panels", "battery", "what inverter"]
        return any(k in msg.lower() for k in keywords)

    def _has_load_data(self, msg: str) -> bool:
        keywords = ["watt", "kw", "kwh", "load", "appliance", "hours per day",
                    "fridge", "lights", "pump", "motor", "tv", "computer"]
        return sum(1 for k in keywords if k in msg.lower()) >= 2

    def _extract_json(self, text: str) -> Optional[dict]:
        text = re.sub(r"^```(?:json)?\n?", "", text.strip())
        text = re.sub(r"\n?```$", "", text)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return None

    def _extract_json_array(self, text: str) -> list:
        text = re.sub(r"^```(?:json)?\n?", "", text.strip())
        text = re.sub(r"\n?```$", "", text)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return []

    def _parse_loads_from_site_data(self) -> list[LoadItem]:
        if not self.extracted_site_data:
            return []
        loads = self.extracted_site_data.get("loads", [])
        return [
            LoadItem(
                name=l.get("name", "Load"),
                wattage=float(l.get("wattage", 0)),
                quantity=int(l.get("quantity", 1)),
                hours_per_day=float(l.get("hours_per_day", 1)),
            )
            for l in loads
            if float(l.get("wattage", 0)) > 0
        ]

    def _template_boq(self, result: SizingResult) -> list[dict]:
        """Exact 14-category quantities-only fallback BOQ based on sizing result."""
        return generate_boq(result.to_dict(), "Solar PV System")

    def get_conversation_history(self) -> list[dict]:
        """Returns conversation history as list of dicts for DB storage."""
        if self.active_engine in ("featherless", "github-gpt-4o"):
            return [{"role": m["role"], "content": m["content"]} for m in self.gpt_history if m["role"] != "system"]
        
        history = []
        if self.gemini_chat:
            try:
                for msg in self.gemini_chat.get_history():
                    role = msg.role
                    text = ""
                    for part in msg.parts:
                        if hasattr(part, "text"):
                            text += part.text
                    history.append({"role": role, "content": text})
            except Exception:
                pass
        return history
