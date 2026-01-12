"""Agent module.

Provides the Mother AI agent with:
- Multi-LLM provider support
- Persistent sessions
- Cognitive reasoning (reflection, goal decomposition)
- Semantic memory
"""

from .cognitive import CognitiveEngine, Confidence, ThinkingMode
from .core import MotherAgent
from .errors import AgentError, ErrorCategory, ErrorHandler
from .session import Session, SessionStore

__all__ = [
    "MotherAgent",
    "AgentError",
    "ErrorCategory",
    "ErrorHandler",
    "CognitiveEngine",
    "Confidence",
    "ThinkingMode",
    "Session",
    "SessionStore",
]
