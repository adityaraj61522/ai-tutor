"""
Gemini service wrapper.

Provides a thin abstraction over LangChain's Google Generative AI integration,
exposing two interaction modes:
  - generate()  – single prompt/response
  - chat()      – multi-turn conversation history

A module-level singleton is managed via get_gemini_service() to avoid
re-creating the heavy LangChain model object on every request.
"""

import logging
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class GeminiService:
    """Wrapper around Google Gemini 2.5 Flash for single-turn and multi-turn chat."""

    def __init__(self) -> None:
        """
        Initialise the Gemini service.

        Reads GOOGLE_API_KEY from the environment.

        Raises:
            ValueError: If GOOGLE_API_KEY is not set.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.7,
        )
        logger.info("GeminiService initialised with model 'gemini-2.5-flash'.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Send a single prompt to Gemini and return the text response.

        Args:
            prompt:        The user message / question.
            system_prompt: Optional system-level instruction to prepend.

        Returns:
            The model's reply as a plain string.
        """
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
            logger.debug("generate: system prompt provided (%d chars).", len(system_prompt))

        messages.append(HumanMessage(content=prompt))
        logger.debug("generate: invoking model with prompt (%d chars).", len(prompt))

        response = self.model.invoke(messages)
        logger.debug("generate: received response (%d chars).", len(response.content))
        return response.content

    def chat(self, messages: list[dict]) -> str:
        """
        Send a multi-turn conversation history to Gemini and return the reply.

        Args:
            messages: List of message dicts, each with:
                        - "role"    : one of "system" | "user" | "human" | "assistant"
                        - "content" : the message text

        Returns:
            The model's reply as a plain string.

        Notes:
            - "system"    → SystemMessage
            - "user" / "human" → HumanMessage
            - "assistant" → AIMessage  (represents a prior model turn)
        """
        langchain_messages = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role in ("user", "human"):
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                # Use AIMessage so the model correctly interprets prior responses
                langchain_messages.append(AIMessage(content=content))
            else:
                logger.warning("chat: unknown role '%s' – message skipped.", role)
                continue

        logger.debug("chat: invoking model with %d message(s).", len(langchain_messages))
        response = self.model.invoke(langchain_messages)
        logger.debug("chat: received response (%d chars).", len(response.content))
        return response.content


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    """
    Return the module-level GeminiService singleton, creating it on first call.

    Returns:
        The shared GeminiService instance.
    """
    global _gemini_service
    if _gemini_service is None:
        logger.info("Creating GeminiService singleton.")
        _gemini_service = GeminiService()
    return _gemini_service
