"""AML Graph Copilot — Root entry point and module for AI Agent.

Delegates to finanse.agent with direct access to all functions and tools.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
FINANSE_DIR = ROOT / "finanse"
if str(FINANSE_DIR) not in sys.path:
    sys.path.insert(0, str(FINANSE_DIR))

from agent import (
    get_node_info,
    find_common_recipients,
    get_cluster_summary,
    ask_aml_agent,
    AGENT_TOOLS,
    SYSTEM_PROMPT,
    DEFAULT_TOKEN,
)

__all__ = [
    "get_node_info",
    "find_common_recipients",
    "get_cluster_summary",
    "ask_aml_agent",
    "AGENT_TOOLS",
    "SYSTEM_PROMPT",
    "DEFAULT_TOKEN",
]

if __name__ == "__main__":
    print("=== AML Graph Copilot (Root Launcher) ===")
    test_q = "Кто аккумулирует средства с клиентов 100000000331309100 и 100000007629096100?"
    print(f"Вопрос: {test_q}\n")
    print(ask_aml_agent(test_q))
