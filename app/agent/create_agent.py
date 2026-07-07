import logging

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.config.langsmith import configure_langsmith_environment
from app.config.settings import settings
from app.middleware.prompt_with_context import prompt_with_context
from app.agent.prompts import BASE_SYSTEM_PROMPT
from app.memory.checkpointer import build_checkpointer
from app.tools.retrieve_context import retrieve_context

logger = logging.getLogger(__name__)


def build_model() -> ChatOpenAI:
    kwargs = {
        "model": settings.chat_model,
        "api_key": settings.openai_api_key,
        "temperature": 0.0,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    logger.info("初始化聊天模型。model=%s 已配置_base_url=%s", settings.chat_model, bool(settings.openai_base_url))
    return ChatOpenAI(**kwargs)

def get_tools():
    return [retrieve_context]


def get_middleware():
    return [prompt_with_context]


def build_agent(*, system_prompt: str | None = None):
    configure_langsmith_environment()
    model = build_model()
    tools = get_tools()
    middleware = get_middleware()
    resolved_system_prompt = system_prompt or BASE_SYSTEM_PROMPT

    agent = create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        checkpointer=build_checkpointer(),
        system_prompt=resolved_system_prompt,
    )
    logger.info(
        "Agent 创建完成。tools=%s middleware_count=%s system_prompt_chars=%s",
        [tool.name for tool in tools],
        len(middleware),
        len(resolved_system_prompt),
    )
    return agent


if __name__ == "__main__":
    # 定义配置，指定 thread_id
    config = {"configurable": {"thread_id": "1"}}
    agent = build_agent()
    print(agent.invoke({"messages": [{"role": "user", "content": "Hi! My name is Bob."}]}, config=config))
