"""Memory manager - high-level API for persistent memory."""

import logging
from datetime import datetime
from typing import Any, Optional

from .store import MemoryStore, Memory
from .embeddings import EmbeddingGenerator

logger = logging.getLogger("mother.memory")


class MemoryManager:
    """
    High-level memory manager for Mother agent.

    Handles:
    - Storing conversation turns with embeddings
    - Retrieving relevant past context
    - Session history management
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.store = MemoryStore()
        self.embeddings = EmbeddingGenerator(
            api_key=openai_api_key,
            model=embedding_model,
        )
        logger.info("Memory manager initialized")

    def remember(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[dict] = None,
        metadata: Optional[dict] = None,
        generate_embedding: bool = True,
    ) -> int:
        """
        Store a memory/observation.

        Args:
            session_id: Current session ID
            role: 'user', 'assistant', or 'tool_result'
            content: The content to remember
            tool_name: Name of tool if this is a tool call/result
            tool_args: Tool arguments if applicable
            metadata: Additional metadata
            generate_embedding: Whether to generate embedding (default True)

        Returns:
            Memory ID
        """
        # Generate embedding for searchability
        embedding = None
        if generate_embedding and content:
            embedding = self.embeddings.generate(content)

        memory = Memory(
            id=None,
            timestamp=datetime.now(),
            session_id=session_id,
            role=role,
            content=content,
            embedding=embedding,
            tool_name=tool_name,
            tool_args=tool_args,
            metadata=metadata,
        )

        memory_id = self.store.add(memory)
        logger.debug(f"Stored memory {memory_id}: {role} ({len(content)} chars)")

        return memory_id

    def remember_user_input(self, session_id: str, content: str) -> int:
        """Store user input."""
        return self.remember(session_id, "user", content)

    def remember_assistant_response(
        self,
        session_id: str,
        content: str,
        tool_calls: Optional[list[dict]] = None,
    ) -> int:
        """Store assistant response."""
        metadata = {"tool_calls": tool_calls} if tool_calls else None
        return self.remember(session_id, "assistant", content, metadata=metadata)

    def remember_tool_result(
        self,
        session_id: str,
        tool_name: str,
        tool_args: dict,
        result: str,
        success: bool = True,
    ) -> int:
        """Store tool execution result."""
        return self.remember(
            session_id=session_id,
            role="tool_result",
            content=result[:2000],  # Truncate long results
            tool_name=tool_name,
            tool_args=tool_args,
            metadata={"success": success},
            generate_embedding=True,
        )

    def recall(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.6,
        exclude_session: Optional[str] = None,
    ) -> list[dict]:
        """
        Recall relevant memories based on semantic similarity.

        Args:
            query: The query to search for
            limit: Maximum memories to return
            min_similarity: Minimum similarity threshold (0-1)
            exclude_session: Session ID to exclude (usually current session)

        Returns:
            List of relevant memories with similarity scores
        """
        # Generate embedding for query
        query_embedding = self.embeddings.generate(query)

        if not query_embedding:
            logger.warning("Failed to generate query embedding")
            return []

        # Search
        results = self.store.search_semantic(
            query_embedding=query_embedding,
            limit=limit,
            min_similarity=min_similarity,
            exclude_session=exclude_session,
        )

        return [
            {
                "memory": memory.to_dict(),
                "similarity": similarity,
                "content": memory.content,
                "role": memory.role,
                "timestamp": memory.timestamp.isoformat(),
            }
            for memory, similarity in results
        ]

    def get_context_for_query(
        self,
        query: str,
        current_session_id: str,
        max_memories: int = 5,
        include_recent: bool = True,
    ) -> str:
        """
        Get formatted context string for injection into agent prompt.

        Args:
            query: Current user query
            current_session_id: Current session to exclude from semantic search
            max_memories: Maximum relevant memories to include
            include_recent: Whether to include recent memories from any session

        Returns:
            Formatted context string for the agent
        """
        context_parts = []

        # Get semantically relevant memories from past sessions
        relevant = self.recall(
            query=query,
            limit=max_memories,
            min_similarity=0.6,
            exclude_session=current_session_id,
        )

        if relevant:
            context_parts.append("## Relevant Past Context")
            for i, mem in enumerate(relevant, 1):
                role = mem["role"]
                content = mem["content"][:500]  # Truncate for context
                timestamp = mem["timestamp"][:10]  # Just date
                similarity = mem["similarity"]

                context_parts.append(
                    f"\n### Memory {i} (relevance: {similarity:.0%}, from {timestamp})"
                )
                context_parts.append(f"**{role.title()}**: {content}")

        # Optionally include recent memories for continuity
        if include_recent:
            recent = self.store.get_recent(limit=3, session_id=None)
            recent = [m for m in recent if m.session_id != current_session_id]

            if recent:
                context_parts.append("\n## Recent Activity")
                for mem in recent[:3]:
                    content = mem.content[:200]
                    context_parts.append(f"- [{mem.role}] {content}")

        if context_parts:
            return "\n".join(context_parts)

        return ""

    def get_session_summary(self, session_id: str) -> Optional[str]:
        """Get a summary of a past session."""
        memories = self.store.get_session_history(session_id)

        if not memories:
            return None

        # Build summary
        user_queries = [m.content for m in memories if m.role == "user"]
        tool_calls = [m.tool_name for m in memories if m.tool_name]

        return f"Session with {len(user_queries)} queries using tools: {set(tool_calls)}"

    def get_stats(self) -> dict:
        """Get memory statistics."""
        return self.store.get_stats()

    def search(self, query: str, limit: int = 10) -> list[Memory]:
        """Simple text search."""
        return self.store.search_text(query, limit)
