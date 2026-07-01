"""KreativOS — shared application state, set by main.py at startup."""
from pathlib import Path
from collections import defaultdict

OLLAMA_BASE_URL: str = "http://localhost:11434"
WORKSPACE_DIR:   Path = None  # type: ignore  # set by main.init_services()

# Services (set by main.py)
memory     = None  # ProjectMemory
scheduler  = None  # TaskScheduler
auth       = None  # AuthManager
skill_eval = None  # SkillEvaluator
audit_log  = None  # AuditLog

# Stats counters (set by main.py)
START_TIME = ""
stats = {}
track: callable = lambda event, detail="": None

# Token usage counters (updated by engine.py)
total_tokens_prompt: int = 0
total_tokens_completion: int = 0
