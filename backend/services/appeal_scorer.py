class AppealScorer:
    """
    Evaluates LLM-extracted legal signals to deterministically calculate 
    an appeal risk score and recommendation.
    """
    
    @staticmethod
    def evaluate(appeal_signals: dict) -> dict:
        if not appeal_signals:
            return {"appeal_consideration": "UNKNOWN", "score": 0, "reasons": ["No signals provided"]}

        score = 0
        reasons = []

        # 1. Quashed Order / Policy Invalidation (+3)
        if str(appeal_signals.get("Order_Quashed", "")).strip().upper() == "YES":
            score += 3
            reasons.append("Government policy or previous order was explicitly quashed.")

        # 2. Financial Liability (+2)
        if str(appeal_signals.get("Financial_Liability", "")).strip().upper() == "YES":
            score += 2
            reasons.append("Financial liability or payout was imposed on the department.")

        # 3. Adverse Ruling (+2)
        if str(appeal_signals.get("Adverse_To_Government", "")).strip().upper() == "YES":
            score += 2
            reasons.append("Judgment contains direct adverse mandates against the government.")
        else:
            # Petition dismissed (govt wins) (-2)
            score -= 2
            reasons.append("Ruling appears favorable to the government (no adverse mandates).")

        # 4. Language Strength Modifiers
        strength = str(appeal_signals.get("Language_Strength", "")).strip().upper()
        if strength == "STRONG":
            score -= 1
            reasons.append("Court used strong language ('settled law', 'no merit'), making appeal difficult.")
        elif strength == "WEAK":
            score += 1
            reasons.append("Court used weaker language ('prima facie'), leaving room for appeal.")

        # 5. Final Decision Logic
        if score >= 3:
            consideration = "HIGH"
        elif 1 <= score <= 2:
            consideration = "MEDIUM"
        else:
            consideration = "LOW"

        return {
            "appeal_consideration": consideration,
            "score": score,
            "reasons": reasons,
            "llm_summary": appeal_signals.get("Reasoning", "No summary provided.")
        }