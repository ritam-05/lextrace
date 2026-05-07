import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


VALID_NATURES = {
    "Policy Update",
    "Financial Payout",
    "Administrative Action",
    "Operational Halt",
    "Mixed",
}

PROMPT_ECHO_MARKERS = {
    "extract the explicit legal mandates",
    "keep them distinct and specific",
    "step 1: what exact administrative action",
    "step 2: are there reports to file",
    "extract explicit time limits",
    "if immediate, write",
    "extract the specific ministries",
    "exclude the petitioner unless",
    "strictly choose one",
}


class ActionPlanGenerator:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(" GROQ_API_KEY missing from .env file.")

        self.client = Groq(api_key=api_key)
        self.model = "llama-3.1-8b-instant"

    @staticmethod
    def _trim_context(context: str, max_chars: int = 24000) -> str:
        """
        Keep the prompt comfortably bounded. RAG context is already ranked, so
        preserving the beginning and end is enough for operative paragraphs that
        spill over adjacent chunks.
        """
        if len(context) <= max_chars:
            return context

        head_size = max_chars // 2
        tail_size = max_chars - head_size
        return (
            context[:head_size]
            + "\n\n[...middle of retrieved context omitted to keep extraction prompt bounded...]\n\n"
            + context[-tail_size:]
        )

    @staticmethod
    def _safe_json_loads(content: str) -> dict:
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            value = json.loads(content[start : end + 1])

        if not isinstance(value, dict):
            raise ValueError("LLM response was valid JSON but not an object.")
        return value

    @staticmethod
    def _list_of_strings(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        cleaned = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            else:
                text = str(item).strip() if item is not None else ""
            if text:
                cleaned.append(text)
        return cleaned

    @staticmethod
    def _contains_prompt_echo(value: Any) -> bool:
        if isinstance(value, dict):
            return any(ActionPlanGenerator._contains_prompt_echo(item) for item in value.values())
        if isinstance(value, list):
            return any(ActionPlanGenerator._contains_prompt_echo(item) for item in value)
        if not isinstance(value, str):
            return False

        normalized = " ".join(value.lower().split())
        return any(marker in normalized for marker in PROMPT_ECHO_MARKERS)

    def _normalize_facts_output(self, result: dict) -> dict:
        extraction = result.get("Extraction")
        action_plan = result.get("Action_Plan")
        if not isinstance(extraction, dict):
            extraction = {}
        if not isinstance(action_plan, dict):
            action_plan = {}

        nature = action_plan.get("Nature_of_Action")
        if nature not in VALID_NATURES:
            nature = "Administrative Action"

        normalized = {
            "Extraction": {
                "Key_Directions": self._list_of_strings(extraction.get("Key_Directions")),
            },
            "Action_Plan": {
                "Compliance_Required": self._list_of_strings(action_plan.get("Compliance_Required")),
                "Key_Timelines": self._list_of_strings(action_plan.get("Key_Timelines")),
                "Responsible_Departments": self._list_of_strings(action_plan.get("Responsible_Departments")),
                "Nature_of_Action": nature,
            },
        }

        if self._contains_prompt_echo(normalized):
            raise ValueError("LLM copied extraction instructions into the action plan.")

        return normalized

    @staticmethod
    def _empty_facts_schema() -> dict:
        return {
            "Extraction": {"Key_Directions": []},
            "Action_Plan": {
                "Compliance_Required": [],
                "Key_Timelines": [],
                "Responsible_Departments": [],
                "Nature_of_Action": "Administrative Action",
            },
        }

    def extract_basic_metadata(self, text_chunk: str) -> dict:
        """
        Extracts the Judge's Name, Date of Order, and the Parties Involved
        from a provided text chunk.
        """
        prompt = f"""
        You are a highly precise Legal AI Extraction System. 
        Read the following text excerpt from the beginning of a court judgment.
        Extract the following core metadata entities:
        1. The "Name of the judge" (including initials and honorifics).
        2. The "Date of order".
        3. The "Petitioners" (or Appellants / Applicants).
        4. The "Respondents" (or Defendants / Non-applicants).

        CRITICAL INSTRUCTIONS:
        - If a specific piece of information is missing from the text, output "Not Specified" for strings, or an empty array [] for lists. Do NOT hallucinate.
        - Clean up the party names by removing leading numbering (e.g., "1.", "2.") if present, but retain their full official designations.
        
        Text Excerpt:
        {text_chunk}

        You must return ONLY a valid JSON object matching the exact schema below. Do not add conversational preamble.
        REQUIRED JSON SCHEMA:
        {{
            "Name_of_the_judge": "Extracted name or Not Specified",
            "Date_of_order": "Extracted date or Not Specified",
            "Petitioners": ["Name of Petitioner 1", "Name of Petitioner 2"],
            "Respondents": ["Name of Respondent 1", "Name of Respondent 2"]
        }}
        """

        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f" Metadata extraction failed: {e}")
            # Return a safe fallback schema to prevent downstream pipeline crashes
            return {
                "Name_of_the_judge": "Error", 
                "Date_of_order": "Error",
                "Petitioners": [],
                "Respondents": []
            }

    def _extract_facts(self, context: str, hard_facts: dict = None, retry: bool = True) -> dict:
        """
        Takes the retrieved context and forces the LLM to output a structured JSON Action Plan.
        """
        hard_facts = hard_facts or {}
        context = self._trim_context(context)

        prompt = f"""
        You are a highly precise Legal Data Extraction Engine powering an e-Governance compliance platform.
        Read the retrieved operative portions of a court judgment and extract only actionable administrative directives.

        CRITICAL INSTRUCTIONS:
        1. NO HALLUCINATION: If a specific piece of information (like a deadline or department) is not explicitly stated or clearly inferable from the text, you MUST output "Not Specified" or an empty array [].
        2. ENTITY RESOLUTION: If the text refers to "the respondent" or "the state," attempt to extract the specific department name if it was mentioned earlier in the provided context.
        3. SEPARATION OF CONCERNS: 
           - 'Key_Directions' should be faithful summaries of the judge's actual orders.
           - 'Compliance_Required' must translate those orders into concrete, plain-English steps for a bureaucrat to execute.
        4. STRICT ENUMS: For 'Nature_of_Action', you are strictly limited to the provided list. Do not invent new categories.
        5. DO NOT COPY THE SCHEMA OR THESE INSTRUCTIONS AS OUTPUT VALUES. Every string must be extracted from or directly based on the judgment context.
        
        Case Facts: {json.dumps(hard_facts)}
        Context:
        {context}

        You MUST output ONLY a valid JSON object, no text before/after. Do not include markdown formatting or conversational preamble.
        If the context does not contain an item for an array field, return [] for that array.
        
        REQUIRED JSON SHAPE:
        {{
            "Extraction": {{
                "Key_Directions": []
            }},
            "Action_Plan": {{
                "Compliance_Required": [],
                "Key_Timelines": [],
                "Responsible_Departments": [],
                "Nature_of_Action": "Policy Update | Financial Payout | Administrative Action | Operational Halt | Mixed"
            }}
        }}
        """

        print(" Transmitting context to Groq LLM for comprehensive extraction...")

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You extract court compliance data. Return only valid JSON. "
                            "Never echo placeholders, schemas, or instructions."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            result = self._safe_json_loads(response.choices[0].message.content)
            result = self._normalize_facts_output(result)
            print(" Successfully generated comprehensive extraction with action plan.")
            return result

        except (json.JSONDecodeError, ValueError) as e:
            if retry:
                print(f" LLM extraction output was invalid ({e}). Retrying with a stricter prompt.")
                retry_context = (
                    "Extract actual directives from the judgment context below. "
                    "Do not output any sentence from the prompt or JSON schema.\n\n"
                    f"{context}"
                )
                return self._extract_facts(retry_context, hard_facts, retry=False)

            print(" LLM failed to produce a usable extraction. Falling back to empty schema.")
            return self._empty_facts_schema()

        
    def _analyze_appeal_risk(self, context: str, extracted_directions: list) -> dict:
        """STAGE 2: Subjective legal analysis based on context and extracted facts."""
        prompt = f"""
        You are an expert Legal Analyst evaluating a judgment for appeal risks.
        Review the context and the specific directions issued by the court.
        
        Court Directions: {json.dumps(extracted_directions)}
        Context:
        {context}

        REQUIRED JSON SCHEMA:
        {{
            "Adverse_To_Government": "Strictly 'Yes' or 'No'. Did the government lose or receive a mandate?",
            "Financial_Liability": "Strictly 'Yes' or 'No'. Is there a payout or financial penalty imposed?",
            "Order_Quashed": "Strictly 'Yes' or 'No'. Was a previous government order or policy invalidated?",
            "Language_Strength": "Strictly choose one: 'Strong' (settled law), 'Weak' (prima facie), or 'Neutral'.",
            "Reasoning": "1-2 sentences explaining the outcome and impact."
        }}
        """
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        return json.loads(response.choices[0].message.content)
    
    def generate(self, context: str, hard_facts: dict = None) -> dict:
        """
        Orchestrates the Prompt Chain: 
        1. Fact Extraction -> 2. Risk Analysis -> 3. JSON Assembly
        """
        hard_facts = hard_facts or {}
        print(" [LLM] Stage 1: Transmitting context for Fact Extraction...")
        
        try:
            # Run Stage 1
            facts_output = self._extract_facts(context, hard_facts)
            
            # Safely grab the directions to pass to Stage 2
            directions = facts_output.get("Extraction", {}).get("Key_Directions", [])
            
            print(" [LLM] Stage 2: Analyzing Extracted Facts for Appeal Risk...")
            # Run Stage 2
            risk_signals = self._analyze_appeal_risk(context, directions)
            
            # Combine the results into the final expected payload
            final_result = {
                "Extraction": facts_output.get("Extraction", {}),
                "Action_Plan": facts_output.get("Action_Plan", {}),
                "Appeal_Risk_Signals": risk_signals
            }
            
            print(" [LLM] Successfully completed two-stage prompt chain.")
            return final_result

        except json.JSONDecodeError:
            print(" [LLM] JSON decoding failed during the prompt chain.")
            return {}


        except Exception as e:
            print(f" Groq API Error: {e}")
            raise e
