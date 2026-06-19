"""
CarbonCoach agent: a reason-act-observe loop over Gemini with carbon-tracking tools.

The agent never invents CO2e numbers itself — every figure comes from
emissions_engine via the tool functions in services.tools. Gemini's job is to
map natural language to the right tool calls and to write the human-facing reply.
"""

import json
import logging
import os
import re

from google import genai
from google.genai import errors, types

from services.emissions_engine import list_activities
from services.storage_service import DEFAULT_USER_ID, storage
from services.tools import (
    tool_calculate_emissions,
    tool_compare_to_average,
    tool_get_history,
    tool_log_activity,
    tool_suggest_swaps,
)

logger = logging.getLogger("carboncoach.agent")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_TOOL_ITERATIONS = 6


def _activity_catalog_text() -> str:
    catalog = list_activities()
    lines = []
    for category, activities in catalog.items():
        items = ", ".join(f"{key} ({v['unit']})" for key, v in activities.items())
        lines.append(f"- {category}: {items}")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You are CarbonCoach, a friendly assistant that helps a person
understand, track, and reduce their personal carbon footprint.

You have tools to calculate emissions, log activities, fetch history, compare to
benchmarks, and suggest swaps. ALWAYS use these tools to get numbers — never invent
or estimate a CO2e figure yourself.

Valid (category, activity) pairs and their units:
{_activity_catalog_text()}

Guidelines:
- When the user describes one or more activities from their day (e.g. "drove 15km
  to work and had a beef burger for lunch"), map each to the closest matching
  (category, activity) pair above, estimate a reasonable quantity if not given
  exactly, call calculate_emissions to get the CO2e, then call log_activity to
  record it.
- If a quantity isn't given, use a sensible default (e.g. one meal = 1, one
  shower = 1) and mention the assumption briefly.
- After logging, give a short, friendly summary of what was logged and its CO2e.
- If the user asks about their progress, totals, or history, call get_history
  and/or compare_to_average and summarize in plain language.
- If the user asks for advice on reducing their footprint, call suggest_swaps and
  present the suggestions with their quantified savings.
- Keep replies concise (2-4 sentences) unless the user asks for detail. Use kg
  CO2e as the unit. End with one concrete, quantified tip when relevant.
"""


def _function_declarations() -> list[types.Tool]:
    return [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="calculate_emissions",
                description="Calculate kg CO2e for a single activity and quantity, without logging it.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "category": types.Schema(type=types.Type.STRING, description="e.g. transport, food, energy, shopping, waste"),
                        "activity": types.Schema(type=types.Type.STRING, description="activity key, e.g. car_petrol_medium, beef"),
                        "quantity": types.Schema(type=types.Type.NUMBER, description="amount in the activity's unit"),
                    },
                    required=["category", "activity", "quantity"],
                ),
            ),
            types.FunctionDeclaration(
                name="log_activity",
                description="Calculate and permanently log an activity for the user's history.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "category": types.Schema(type=types.Type.STRING),
                        "activity": types.Schema(type=types.Type.STRING),
                        "quantity": types.Schema(type=types.Type.NUMBER),
                        "note": types.Schema(type=types.Type.STRING, description="optional short note, e.g. original user phrase"),
                    },
                    required=["category", "activity", "quantity"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_history",
                description="Get the user's logged activity totals for a period.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "period": types.Schema(type=types.Type.STRING, description="one of: today, week, month, year"),
                    },
                    required=["period"],
                ),
            ),
            types.FunctionDeclaration(
                name="compare_to_average",
                description="Compare the user's annualized footprint (based on the last week) to country/global averages and the Paris target.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "country": types.Schema(type=types.Type.STRING, description="optional, e.g. usa, uk, india, eu, global"),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="suggest_swaps",
                description="Suggest quantified lower-carbon swaps based on the user's last month of activity.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "top_n": types.Schema(type=types.Type.INTEGER, description="how many suggestions to return, default 3"),
                    },
                ),
            ),
        ])
    ]


def _dispatch_tool(name: str, args: dict) -> dict:
    if name == "calculate_emissions":
        return tool_calculate_emissions(args["category"], args["activity"], args["quantity"])
    if name == "log_activity":
        return tool_log_activity(
            DEFAULT_USER_ID, args["category"], args["activity"], args["quantity"], args.get("note", "")
        )
    if name == "get_history":
        return tool_get_history(DEFAULT_USER_ID, args.get("period", "week"))
    if name == "compare_to_average":
        return tool_compare_to_average(DEFAULT_USER_ID, args.get("country"))
    if name == "suggest_swaps":
        return tool_suggest_swaps(DEFAULT_USER_ID, args.get("top_n", 3))
    return {"error": f"Unknown tool: {name}"}


class AgentService:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None
        self._tools = _function_declarations()
        if not self.client:
            logger.warning("No GOOGLE_API_KEY/GEMINI_API_KEY set — agent will use a basic fallback responder.")

    def chat(self, message: str) -> dict:
        if not self.client:
            return self._fallback(message)

        parts = [types.Part(text=message)]
        return self._run_loop(parts)

    def chat_with_image(self, message: str, image_bytes: bytes, mime_type: str) -> dict:
        if not self.client:
            return {
                "reply": "Photo logging needs GEMINI_API_KEY to be set (Gemini vision identifies the items).",
                "actions": [],
            }

        prompt = message or (
            "Identify the food or activity shown in this photo, map it to the closest "
            "(category, activity) pair from the catalog, estimate a reasonable quantity, "
            "calculate its emissions, and log it."
        )
        parts = [
            types.Part(text=prompt),
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ]
        return self._run_loop(parts)

    def _run_loop(self, initial_parts: list[types.Part]) -> dict:
        contents: list[types.Content] = [
            types.Content(role="user", parts=initial_parts)
        ]
        actions = []

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = self.client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=self._tools,
                    ),
                )
            except errors.ClientError as e:
                logger.error(f"Gemini API error: {e}")
                if e.code == 429:
                    reply = (
                        "Gemini API quota/credits are exhausted for this key. "
                        "Check billing at https://ai.studio/projects, or set a key from a "
                        "project with available quota."
                    )
                else:
                    reply = f"Gemini API error ({e.code}): {e.message}"
                return {"reply": reply, "actions": actions}

            candidate = response.candidates[0]
            parts = candidate.content.parts
            function_calls = [p.function_call for p in parts if p.function_call]

            if not function_calls:
                reply = "".join(p.text or "" for p in parts).strip()
                return {"reply": reply, "actions": actions}

            contents.append(candidate.content)

            function_response_parts = []
            for fc in function_calls:
                args = dict(fc.args or {})
                result = _dispatch_tool(fc.name, args)
                actions.append({"tool": fc.name, "args": args, "result": result})
                function_response_parts.append(
                    types.Part.from_function_response(name=fc.name, response={"result": result})
                )
            contents.append(types.Content(role="user", parts=function_response_parts))

        return {
            "reply": "I gathered some data but ran out of steps — try asking again, maybe more specifically.",
            "actions": actions,
        }

    # --- fallback for when no Gemini API key is configured ---

    _FALLBACK_PATTERNS = [
        (re.compile(r"(\d+(?:\.\d+)?)\s*km", re.I), "transport", "car_petrol_medium", "km"),
        (re.compile(r"\bbeef\b|\bburger\b|\bsteak\b", re.I), "food", "beef", "meal"),
        (re.compile(r"\bchicken\b", re.I), "food", "chicken", "meal"),
        (re.compile(r"\bvegetarian\b|\bveggie\b", re.I), "food", "vegetarian", "meal"),
        (re.compile(r"\bvegan\b", re.I), "food", "vegan", "meal"),
    ]

    def _fallback(self, message: str) -> dict:
        actions = []
        for pattern, category, activity, unit in self._FALLBACK_PATTERNS:
            match = pattern.search(message)
            if not match:
                continue
            quantity = float(match.group(1)) if match.groups() else 1.0
            result = tool_log_activity(DEFAULT_USER_ID, category, activity, quantity, note=message)
            actions.append({"tool": "log_activity", "args": {"category": category, "activity": activity, "quantity": quantity}, "result": result})

        if actions:
            total = sum(a["result"]["co2e_kg"] for a in actions)
            reply = (
                f"Logged {len(actions)} activity(ies) totalling {round(total, 2)} kg CO2e. "
                "(Running in fallback mode — set GEMINI_API_KEY for full conversational understanding.)"
            )
        else:
            reply = (
                "I'm running in fallback mode (no GEMINI_API_KEY set), so I can only recognize a few "
                "simple patterns like 'drove 10km' or 'had a beef burger'. Set GEMINI_API_KEY for full "
                "conversational tracking and advice."
            )
        return {"reply": reply, "actions": actions}


agent_service = AgentService()
