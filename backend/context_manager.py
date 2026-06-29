"""
KreativOS — Context Window Manager (Phase 1)

Prevents silent context overflow by estimating token counts and trimming
the oldest decisions/notes first when approaching the model's limit.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Conservative limit for CPU-only models (many have 4096 context)
MAX_CONTEXT_TOKENS = 3500
# Rough estimate: 1 token ≈ 4 characters
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def build_full_system_prompt(
    system: str,
    skills: str = "",
    memory_context: str = "",
    search_context: str = "",
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> str:
    """
    Assemble the full system prompt while staying within the token budget.
    Trims memory context (oldest decisions first) if over budget.
    """
    # Fixed parts (always included)
    now  = datetime.now().astimezone()
    base = f"[System date/time: {now:%A, %B %d, %Y at %I:%M:%S %p %Z}]\n\n{system}"
    if skills:
        base += "\n\n" + skills

    base_tokens = estimate_tokens(base)
    remaining   = max_tokens - base_tokens

    if remaining <= 0:
        logger.warning("System prompt alone exceeds token budget — truncating skills")
        return system[:max_tokens * CHARS_PER_TOKEN]

    # Try adding search context
    search_tokens = estimate_tokens(search_context) if search_context else 0
    if search_context and search_tokens <= remaining:
        base += "\n\n" + search_context
        remaining -= search_tokens
    elif search_context:
        # Truncate search context to fit
        allowed_chars = remaining * CHARS_PER_TOKEN
        base += "\n\n" + search_context[:allowed_chars]
        logger.info("Search context truncated to fit token budget")
        remaining = 0

    # Try adding memory context
    if memory_context and remaining > 50:
        memory_tokens = estimate_tokens(memory_context)
        if memory_tokens <= remaining:
            base += "\n\n" + memory_context
        else:
            # Trim memory: keep header + most recent decisions only
            base += "\n\n" + _trim_memory_context(memory_context, remaining)
            logger.info("Memory context trimmed to fit token budget")

    return base


def _trim_memory_context(memory_text: str, max_tokens: int) -> str:
    """
    Trim memory context by dropping oldest decisions first.
    Keeps the section headers and the most recent entries.
    """
    lines     = memory_text.split("\n")
    max_chars = max_tokens * CHARS_PER_TOKEN

    # Always keep the header line
    result = [lines[0]] if lines else []
    budget = max_chars - len(lines[0])

    # Add lines from the end (most recent) backwards
    for line in reversed(lines[1:]):
        if len(line) + 1 <= budget:
            result.insert(1, line)
            budget -= len(line) + 1
        else:
            break

    return "\n".join(result)
