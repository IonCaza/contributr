from __future__ import annotations

from typing import AsyncIterator

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import get_ai_config, build_llm
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import ServiceTools


async def build_agent(db: AsyncSession) -> tuple[AgentExecutor, dict]:
    config = await get_ai_config(db)
    if not config.get("enabled"):
        raise RuntimeError("AI agent is not configured")

    llm = build_llm(config, streaming=True)
    tools = ServiceTools(db).get_tools()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=config.get("max_iterations", 10),
    )
    return executor, config


def history_to_messages(history: list[dict]) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for entry in history:
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))
        elif entry["role"] == "assistant":
            messages.append(AIMessage(content=entry["content"]))
    return messages


async def run_agent_stream(
    db: AsyncSession,
    user_input: str,
    chat_history: list[dict],
) -> AsyncIterator[str]:
    """Run the agent and yield streamed text chunks."""
    executor, _ = await build_agent(db)
    messages = history_to_messages(chat_history)

    collected = ""
    pending_separator = False
    async for event in executor.astream_events(
        {"input": user_input, "chat_history": messages},
        version="v2",
    ):
        kind = event["event"]
        if kind == "on_tool_end":
            if collected:
                pending_separator = True
        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content") and isinstance(chunk.content, str) and chunk.content:
                if pending_separator:
                    collected += "\n\n"
                    yield "\n\n"
                    pending_separator = False
                collected += chunk.content
                yield chunk.content

    if not collected:
        result = await executor.ainvoke(
            {"input": user_input, "chat_history": messages}
        )
        output = result.get("output", "I wasn't able to generate a response.")
        yield output
