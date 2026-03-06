from pathlib import Path

CHAT_DIR = Path(__file__).parent

MAX_FEEDBACK_LOOPS = 3

DEBUG = True

# False for old models like Claude Haiku
EXTRACTOR_MODEL_SUPPORTS_STRUCTURED_RESPONSES = True

ENABLE_GUARDRAILS = True
