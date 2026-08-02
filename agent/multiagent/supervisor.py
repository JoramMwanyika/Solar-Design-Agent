import json
from typing import Callable, Optional, Tuple, List, Dict, Any
from agent.multiagent.state import ProjectState
from agent.multiagent.agents import ALL_AGENTS, _extract_json
from agent.multiagent.tools.math_tools import get_location_psh

class SupervisorAgent:
    """
    The main orchestrator of the Multiagent System.
    It manages conversational memory, routes user requests to specialized agents,
    runs the agent tool-calling loops, and maintains state synchronization.
    """
    def __init__(self, llm_generate_func: Callable[[str], str]):
        self.generate_content = llm_generate_func

    def _format_history(self, history: Optional[List[Dict[str, str]]]) -> str:
        if not history:
            return "No previous conversation history."
        formatted = []
        recent = history[-8:]
        for msg in recent:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            if len(content) > 600:
                content = content[:600] + "... [truncated]"
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

    def _route(self, user_input: str, state_json: str, history_str: str) -> Tuple[Optional[str], str]:
        """Asks the LLM supervisor to decide the next specialized agent or answer directly."""
        prompt = (
            "You are SolarBot, an expert AI Solar PV Design Engineer and lead orchestrator of a multi-agent solar sizing system.\n"
            "Your role is to converse naturally with the customer, understand their needs, maintain context, and invoke specialized agents/tools when needed.\n\n"
            f"Recent Conversation History:\n{history_str}\n\n"
            f"Current Project State:\n{state_json}\n\n"
            f"New User Request:\n{user_input}\n\n"
            "Available Specialized Agents:\n" + "\n".join([f"- {name}: {agent.role}" for name, agent in ALL_AGENTS.items()]) + "\n\n"
            "Routing Instructions:\n"
            "1. If the user is providing project location, asking questions, seeking engineering advice, or chatting naturally, set next_agent to 'None' and provide a warm, professional, markdown response.\n"
            "2. If the user provides a bill, logger data, load schedule, or requests calculations, route to the relevant specialized agent.\n\n"
            "CRITICAL MATHEMATICAL ACCURACY RULES:\n"
            "- Direct Sizing Formula: Required DC Capacity (kWp) = Daily Energy (kWh) ÷ Peak Sun Hours (h/day). Do NOT include loss factors.\n"
            "- Time-Series Logged Data Rule: Always check the sample time interval (delta_t = interval_minutes / 60) for accurate energy calculation, and select the day with the MAXIMUM power average / highest daily energy for sizing.\n"
            "- Example: 2,285.64 kWh ÷ 3.458 h/day = 660.97 kWp.\n\n"
            "Return ONLY a raw JSON block:\n"
            "If routing: {\"next_agent\": \"Agent Name\", \"reason\": \"...\"}\n"
            "If answering directly: {\"next_agent\": \"None\", \"response\": \"Your detailed conversational answer...\"}"
        )
        
        response_text = self.generate_content(prompt)
        data = _extract_json(response_text)
        if data:
            next_agent = data.get("next_agent", "None")
            detail = data.get("response", data.get("reason", ""))
            return next_agent, detail
        return "None", response_text.strip()

    def process_message(self, user_input: str, state: ProjectState, history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Processes a user message through the multiagent system with full conversational memory.
        Returns the final text response to the user.
        """
        # 1. Quick Location Check & Exact PSH Lookup
        user_lower = user_input.lower()
        if "location" in user_lower or "nairobi" in user_lower or "mombasa" in user_lower or "kilifi" in user_lower:
            loc_data = get_location_psh(user_input)
            state.location = loc_data["location"].replace("Location", "").replace("location", "").strip(" :") or state.location
            state.peak_sun_hours = loc_data["peak_sun_hours"]

        history_str = self._format_history(history)
        state_json = json.dumps(state.to_dict(), indent=2)
        
        next_agent_name, supervisor_response = self._route(user_input, state_json, history_str)
        
        if next_agent_name == "None" or next_agent_name not in ALL_AGENTS:
            # If state has location updated but no loads yet, build a clean friendly response
            if ("location" in user_lower or "nairobi" in user_lower) and state.daily_energy_kwh == 0 and not state.loads:
                return (
                    f"Got it! I've updated the project location to **{state.location}** "
                    f"(Peak Sun Hours: **{state.peak_sun_hours} h/day**).\n\n"
                    f"To calculate your solar PV system size and Bill of Quantities (BOQ), please:\n"
                    f"- 📎 Upload a `.csv` / `.xlsx` load schedule or logger data file, or\n"
                    f"- 💬 Tell me about your appliances (e.g. *'I have 5 lights, 2 fridges, and a 1.5kW pump'*)."
                )
            return supervisor_response
            
        agent = ALL_AGENTS[next_agent_name]
        
        # Agent execution loop (Tool calling ReAct loop)
        max_iterations = 5
        iteration = 0
        agent_context = (
            f"Recent Conversation History:\n{history_str}\n\n"
            f"User Request: {user_input}\n"
        )
        
        while iteration < max_iterations:
            iteration += 1
            prompt = agent.get_system_prompt(json.dumps(state.to_dict(), indent=2)) + "\n\n" + agent_context
            
            llm_output = self.generate_content(prompt)
            result = agent.process_llm_response(llm_output, state)
            
            if result["type"] == "complete":
                # Clean up response message (remove raw agent prefixes if present)
                msg = result['message']
                if msg.startswith(f"**{agent.name}**"):
                    msg = msg[len(f"**{agent.name}**"):].lstrip(" :")
                return msg
                
            elif result["type"] == "tool_call":
                agent_context += f"\nTool executed: {result['tool']}\nResult: {json.dumps(result['result'])}\n"
                
            elif result["type"] == "tool_error":
                agent_context += f"\nTool error: {result['tool']} failed - {result['error']}\n"
                
            else:
                return result.get('message', llm_output.strip())
                
        return f"Completed analysis for your request."
