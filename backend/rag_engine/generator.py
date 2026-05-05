import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class ActionPlanGenerator:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("❌ GROQ_API_KEY missing from .env file.")
        
        self.client = Groq(api_key=api_key)
        # Using LLaMA 3 8B. It's incredibly fast on Groq and strictly follows JSON schemas.
        self.model = "llama-3.1-8b-instant" 

    def generate(self, context: str, hard_facts: dict = None) -> dict:
        """
        Takes the retrieved context and forces the LLM to output a structured JSON object
        containing both flat arbitration fields and the nested action-plan payload.
        """
        hard_facts = hard_facts or {}
        
        prompt = f"""
        You are a highly analytical legal AI system for the Indian justice department.
        Your task is to extract BOTH case metadata AND action plan from the provided context.
        
        Previous Hard Facts (from Regex): {json.dumps(hard_facts)}
        
        Context (operative section):
        {context}
        
        You must return ONLY a valid JSON object matching the exact schema below. Do not output markdown code blocks. Do not add conversational preamble.
        Extract with high precision - these will be compared with regex extraction.
        
        {{
            "case_number": "extracted case number if found",
            "court_name": "extracted court name if found",
            "bench": "extracted bench/judge names if found",
            "judgment_date": "extracted judgment date if found",
            "petitioner": "extracted petitioner name if found",
            "respondent": "extracted respondent name if found",
            "directives": ["list of explicit orders or actions commanded by the court"],
            "responsible_departments": ["list of government or police departments mentioned for action"],
            "deadlines": ["list of mentioned dates, timelines, or compliance periods"],
            "status": "pending_review",
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
        
        print("🧠 Transmitting context to Groq LLM for comprehensive extraction...")
        
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                # Enforces native JSON output from the model
                response_format={"type": "json_object"}, 
                temperature=0.0 # Strict determinism, no creative hallucinations
            )
            
            # The JSON object is returned as a string, parse it into a Python dict
            result = json.loads(response.choices[0].message.content)
            print("✅ Successfully generated comprehensive extraction with action plan.")
            return result
            
        except json.JSONDecodeError:
            print("❌ LLM failed to output valid JSON. Falling back to empty schema.")
            return {
                "case_number": "",
                "court_name": "",
                "bench": "",
                "judgment_date": "",
                "petitioner": "",
                "respondent": "",
                "directives": ["Error parsing LLM output"], 
                "responsible_departments": [], 
                "deadlines": [], 
                "status": "failed_generation",
                "Extraction": {
                    "Date_of_Order": "",
                    "Parties_Involved": [],
                    "Key_Directions": [],
                },
                "Action_Plan": {
                    "Compliance_Required": "",
                    "Consideration_for_Appeal": "Not Specified",
                    "Key_Timelines": [],
                    "Responsible_Departments": [],
                    "Nature_of_Action": "",
                },
            }
        except Exception as e:
            print(f"❌ Groq API Error: {e}")
            raise e