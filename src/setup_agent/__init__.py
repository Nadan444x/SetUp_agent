"""SetUp Agent — a terminal agent that provisions a fresh Mac using a local LLM.

Two layers:
  * Layer 0  bootstrap.sh  — dumb shell that installs the prerequisites (brew, python,
    ollama, a model, and this package) on a bare machine.
  * Layer 1  setup-agent   — this package: the smart, LLM-driven provisioner.

The brain is a local model served by Ollama. It never runs commands itself; it emits
tool calls that a Python executor runs behind a safety layer, feeding results back in a
loop until the machine matches the living `Setup.md` profile.
"""

__version__ = "0.1.0"

DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_PROFILE = "Setup.md"
