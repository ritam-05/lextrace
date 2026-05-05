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
        Extracts the Judge's Name and Date of Order from a provided text chunk.
        """
        prompt = f"""
        You are a Legal AI Extraction System. 
        Read the following text excerpt from the beginning of a court judgment.
        Extract the "Name of the judge (including initials)" and the "Date of order".
        If a piece of information is missing, output "Not Specified".
        
        Text Excerpt:
        {text_chunk}

        You must return ONLY a valid JSON object matching the exact schema below. Do not add conversational preamble.
        REQUIRED JSON SCHEMA:
        {{
            "Name_of_the_judge": "Extracted name or Not Specified",
            "Date_of_order": "Extracted date or Not Specified"
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
            return {"Name_of_the_judge": "Error", "Date_of_order": "Error"}

    def _extract_facts(self, context: str, hard_facts: dict = None) -> dict:
        """
        Takes the retrieved context and forces the LLM to output a structured JSON Action Plan.
        """
        hard_facts = hard_facts or {}

        prompt = f"""
        You are a highly precise Legal AI Extraction System designed for government administration. 
        Your sole objective is to read excerpts from a court judgment and extract actionable directives.
        CRITICAL INSTRUCTIONS:
        1. IGNORE all background facts, historical case citations, and appellant/respondent arguments.
        2. FOCUS EXCLUSIVELY on extracting the final orders, directions, compliance requirements, and timelines.
        3. If a specific piece of information is not present in the text, output "Not Specified". Do NOT hallucinate.
        4. You MUST output your response as a valid JSON object matching the exact schema below.
        
        Case Facts: {json.dumps(hard_facts)}
        Context:
        {context}

        You must return ONLY a valid JSON object matching the exact schema below. Do not output markdown code blocks. Do not add conversational preamble.
        REQUIRED JSON SCHEMA:
        {{
            "Extraction": {{
            "Parties_Involved": ["Party 1", "Party 2, etc"],
            "Key_Directions": ["Direction 1", "Direction 2, etc"]
        }},
          "Action_Plan": {{
            "Compliance_Required": "What specifically needs to be done? (Provide short supporting points)",
            "Key_Timelines": ["Timeline 1", "Timeline 2"],
            "Responsible_Departments": ["Dept 1", "Dept 2"],
            "Nature_of_Action": "Categorize as: Policy Update, Financial Payout, Administrative Action, or Operational Halt"
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
