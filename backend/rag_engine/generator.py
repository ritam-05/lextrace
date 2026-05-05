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

    def generate(self, context: str, hard_facts: dict = None) -> dict:
        """
        Takes the retrieved context and forces the LLM to output a structured JSON Action Plan.
        """
        hard_facts = hard_facts or {}

        prompt = f"""
        You are a highly precise Legal AI Extraction System designed for government administration. 
        Your sole objective is to read excerpts from a court judgment and extract actionable directives.
        CRITICAL INSTRUCTIONS:
        1. IGNORE all background facts, historical case citations, and appellant/respondent arguments.
        2. FOCUS EXCLUSIVELY on the final orders, directions, compliance requirements, and timelines.
        3. If a specific piece of information is not present in the text, output "Not Specified". Do NOT hallucinate.
        4. You MUST output your response as a valid JSON object matching the exact schema below.
        
        Case Facts: {json.dumps(hard_facts)}
        Context:
        {context}

        You must return ONLY a valid JSON object matching the exact schema below. Do not output markdown code blocks. Do not add conversational preamble.
        REQUIRED JSON SCHEMA:
        {{
            "Extraction": {{
            "Date_of_Order": "Exact date if mentioned",
            "Parties_Involved": ["Party 1", "Party 2"],
            "Key_Directions": ["Direction 1", "Direction 2"]
        }},
          "Action_Plan": {{
            "Compliance_Required": "What specifically needs to be done?",
            "Consideration_for_Appeal": "Is there a mention of appealing to a higher court? (Yes/No/Not Specified)",
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
        except Exception as e:
            print(f" Groq API Error: {e}")
            raise e
