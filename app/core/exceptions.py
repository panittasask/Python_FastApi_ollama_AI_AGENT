"""Custom exceptions."""


class AgentAPIError(Exception):
    """Base error."""


class OllamaError(AgentAPIError):
    """Ollama backend error."""


class GenerationError(AgentAPIError):
    """Generation failure."""


class PlanError(AgentAPIError):
    """Plan management error."""


class FileOperationError(AgentAPIError):
    """File operation failure."""
