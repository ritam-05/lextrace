import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


class ActionPlanGenerator:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(" GROQ_API_KEY missing from .env file.")

        self.client = Groq(api_key=api_key)
        self.model = "llama-3.1-8b-instant"

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

    def _extract_facts(self, context: str, hard_facts: dict = None) -> dict:
        """
        Takes the retrieved context and forces the LLM to output a structured JSON Action Plan.
        """
        hard_facts = hard_facts or {}

        prompt = f"""
        You are a highly precise Legal Data Extraction Engine powering an e-Governance compliance platform. 
        Your sole objective is to read the operative portion of a court judgment and extract actionable, administrative directives into a strict JSON schema.

        CRITICAL INSTRUCTIONS:
        1. NO HALLUCINATION: If a specific piece of information (like a deadline or department) is not explicitly stated or clearly inferable from the text, you MUST output "Not Specified" or an empty array [].
        2. ENTITY RESOLUTION: If the text refers to "the respondent" or "the state," attempt to extract the specific department name if it was mentioned earlier in the provided context.
        3. SEPARATION OF CONCERNS: 
           - 'Key_Directions' should be faithful summaries of the judge's actual orders.
           - 'Compliance_Required' must translate those orders into concrete, plain-English steps for a bureaucrat to execute.
        4. STRICT ENUMS: For 'Nature_of_Action', you are strictly limited to the provided list. Do not invent new categories.
        
        Case Facts: {json.dumps(hard_facts)}
        Context:
        {context}

        You MUST output ONLY a valid JSON object, no text before/after. Do not include markdown formatting or conversational preamble.
        
        REQUIRED JSON SCHEMA:
        {{
            "Extraction": {{
                "Key_Directions": [
                    "Extract the explicit legal mandates, injunctions, or orders issued by the court.",
                    "Keep them distinct and specific."
                ]
            }},
            "Action_Plan": {{
                "Compliance_Required": [
                    "Step 1: What exact administrative action must the department take?",
                    "Step 2: Are there reports to file, money to disburse, or records to update?"
                ],
                "Key_Timelines": [
                    "Extract explicit time limits (e.g., 'within 4 weeks', 'by 15th August').",
                    "If immediate, write 'Forthwith / Immediate'."
                ],
                "Responsible_Departments": [
                    "Extract the specific ministries, boards, or departments ordered to act.",
                    "Exclude the petitioner unless they are a government body."
                ],
                "Nature_of_Action": "STRICTLY choose ONE from: ['Policy Update', 'Financial Payout', 'Administrative Action', 'Operational Halt', 'Mixed']"
            }}
        }}
        """

        print(" Transmitting context to Groq LLM for comprehensive extraction...")

        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            result = json.loads(response.choices[0].message.content)
            print(" Successfully generated comprehensive extraction with action plan.")
            return result

        except json.JSONDecodeError:
            print(" LLM failed to output valid JSON. Falling back to empty schema.")
            return {
                "directives": ["Error parsing LLM output"], 
                "responsible_departments": [], 
                "deadlines": [], 
                "status": "failed_generation"
            }

        
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
