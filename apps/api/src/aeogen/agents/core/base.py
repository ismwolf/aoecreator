"""Agent base class.

Owns invariants (ClassVar fields), callback wiring, and the abstract `run()`.
Concrete agents (Faz 5 E) subclass this.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from langchain_core.callbacks import AsyncCallbackHandler
from pydantic import BaseModel

from aeogen.agents.core.protocols import LLMProvider, MemoryBackend, SkillProvider
from aeogen.agents.core.types import AgentContext

AgentKind = Literal["analyzer", "generator", "orchestrator"]


class Agent(ABC):
    """Base for every GEO agent.

    Subclasses MUST declare the four ClassVars below.
    Enforcement runs in `__init_subclass__` — invalid subclasses raise at class
    definition time (not first instantiation), so misconfigurations fail fast.
    """

    name: ClassVar[str]
    technique_id: ClassVar[int | None]  # 1-12 (master plan §1), None for orchestrators
    kind: ClassVar[AgentKind]
    default_llm: ClassVar[str]  # OpenRouter model id, e.g., "anthropic/claude-sonnet-4-6"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            return  # abstract subclasses (rare) skip the check
        required = ("name", "technique_id", "kind", "default_llm")
        missing = [f for f in required if f not in cls.__dict__]
        if missing:
            raise TypeError(f"Agent subclass {cls.__name__} missing ClassVars: {missing}")
        if cls.kind not in ("analyzer", "generator", "orchestrator"):
            raise TypeError(f"{cls.__name__}.kind must be analyzer/generator/orchestrator")
        if cls.technique_id is not None and not (1 <= cls.technique_id <= 12):
            raise TypeError(f"{cls.__name__}.technique_id must be 1-12 or None")

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryBackend,
        skills: SkillProvider,
        *,
        callbacks: list[AsyncCallbackHandler] | None = None,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.skills = skills
        self.callbacks: list[AsyncCallbackHandler] = callbacks or []

    @abstractmethod
    async def run(self, input: BaseModel, ctx: AgentContext) -> BaseModel:
        """Execute the agent's workflow.

        Concrete agents (Faz 5 E) typically build a LangGraph StateGraph here
        and invoke it with `config={"callbacks": self.callbacks, "configurable":
        {"thread_id": str(ctx.execution_id)}}`.
        """
        ...
