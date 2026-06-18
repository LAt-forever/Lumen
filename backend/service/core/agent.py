from __future__ import annotations

import json

from service.core.global_search import GlobalSearchService
from service.core.memory import MemoryService
from service.repositories.agent import AgentRepository
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.sources import SourceRepository
from service.schemas import AgentRunResponse, AgentToolLogRead, MemoryRead


class AgentService:
    def __init__(
        self,
        agent: AgentRepository,
        sources: SourceRepository,
        chunks: ChunkRepository,
        memories: MemoryRepository,
        conversations: ConversationRepository,
        organization: OrganizationRepository,
    ):
        self.agent = agent
        self.sources = sources
        self.chunks = chunks
        self.memories = memories
        self.conversations = conversations
        self.organization = organization

    def run(self, message: str) -> AgentRunResponse:
        profile = self.agent.active_or_default()
        enabled_tools = set(self.agent.enabled_tools(profile))
        used_tools: list[str] = []
        logs = []
        search_results = []
        memory_rows = []
        graph = None

        if "global_search" in enabled_tools:
            search_service = GlobalSearchService(self.sources, self.chunks, self.memories, self.conversations, self.organization)
            search_results = search_service.search(message, limit=5)
            used_tools.append("global_search")
            logs.append(
                self.agent.create_tool_log(
                    profile.id,
                    "global_search",
                    "search",
                    json.dumps({"query": message, "limit": 5}, ensure_ascii=False),
                    result_summary=f"返回 {len(search_results)} 条结果",
                )
            )

        memory_service = MemoryService(self.memories)
        if "memory_search" in enabled_tools:
            memory_rows = memory_service.search(message, limit=5)
            used_tools.append("memory_search")
            logs.append(
                self.agent.create_tool_log(
                    profile.id,
                    "memory_search",
                    "search",
                    json.dumps({"query": message, "limit": 5}, ensure_ascii=False),
                    result_summary=f"返回 {len(memory_rows)} 条记忆",
                )
            )

        if "memory_graph" in enabled_tools and memory_rows:
            graph = memory_service.build_memory_graph(memory_rows[0].id, depth=2)
            used_tools.append("memory_graph")
            logs.append(
                self.agent.create_tool_log(
                    profile.id,
                    "memory_graph",
                    "expand",
                    json.dumps({"center_memory_id": memory_rows[0].id, "depth": 2}, ensure_ascii=False),
                    result_summary=f"返回 {len(graph.nodes)} 个节点和 {len(graph.edges)} 条关系",
                )
            )

        answer = self._answer(message, used_tools, search_results, memory_rows)
        return AgentRunResponse(
            answer=answer,
            used_tools=used_tools,
            search_results=search_results,
            memories=[MemoryRead.model_validate(memory) for memory in memory_rows],
            graph=graph,
            tool_logs=[AgentToolLogRead.model_validate(log) for log in logs],
        )

    def _answer(self, message: str, used_tools: list[str], search_results: list, memory_rows: list) -> str:
        if not used_tools:
            return "当前 Agent 未启用任何工具。请在 Agent 配置中开启只读工具后再运行。"
        if not search_results and not memory_rows:
            return f"我运行了 {self._tool_label(used_tools)}，但没有找到足够证据回答「{message}」。"
        parts = [f"我运行了 {self._tool_label(used_tools)}。"]
        if search_results:
            top = search_results[0]
            parts.append(f"最相关资料是「{top.title}」：{top.snippet[:180]}")
        if memory_rows:
            parts.append(f"相关记忆：{memory_rows[0].text}")
        return "\n".join(parts)

    def _tool_label(self, tools: list[str]) -> str:
        labels = {
            "global_search": "全局搜索",
            "memory_search": "记忆搜索",
            "memory_graph": "记忆图谱",
        }
        return "、".join(labels.get(tool, tool) for tool in tools)
