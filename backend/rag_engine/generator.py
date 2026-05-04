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

    def generate(self, context: str, hard_facts: dict) -> dict:
        """
        Takes the retrieved context and forces the LLM to output a structured JSON Action Plan.
        """
        prompt = f"""
        You are a highly analytical legal AI system for the Indian justice department.
        Your task is to extract a structured action plan based ONLY on the provided Context from a court judgment.
        
        Case Facts: {json.dumps(hard_facts)}
        
        Context:
        {context}
        
        You must return ONLY a valid JSON object matching the exact schema below. Do not output markdown code blocks. Do not add conversational preamble.
        
        {{
            "directives": ["list of explicit orders or actions commanded by the court"],
            "responsible_departments": ["list of government or police departments mentioned for action"],
            "deadlines": ["list of mentioned dates, timelines, or compliance periods"],
            "status": "pending_review"
        }}
        """
        
        print("🧠 Transmitting context to Groq LLM for Action Plan extraction...")
        
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
            print("✅ Successfully generated JSON Action Plan.")
            return result
            
        except json.JSONDecodeError:
            print("❌ LLM failed to output valid JSON. Falling back to empty schema.")
            return {
                "directives": ["Error parsing LLM output"], 
                "responsible_departments": [], 
                "deadlines": [], 
                "status": "failed_generation"
            }
        except Exception as e:
            print(f"❌ Groq API Error: {e}")
            raise e