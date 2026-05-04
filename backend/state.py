# backend/state.py

# Global dictionary to hold the loaded model in memory.
# Extracted here to prevent circular imports between app.py and services.
ml_models = {}