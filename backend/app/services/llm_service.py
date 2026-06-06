"""
LLM 服务：封装 Qwen3 via DashScope OpenAI 兼容接口
依据 ADR-001（接入方式）+ ADR-002（字段规范）
"""
from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache(maxsize=4)
def get_qwen3_chat_model(
    model: str | None = None,
    temperature: float = 0.2,
    streaming: bool = True,
) -> ChatOpenAI:
    """
    获取 Qwen3 ChatOpenAI 单例

    Args:
        model: 模型名，默认从 settings.QWEN_MODEL 读取
        temperature: 温度（NL2SQL 建议 0.1~0.3）
        streaming: 是否流式（流式需要 stream_usage 显式开启才能拿 token）
    """
    s = get_settings()
    return ChatOpenAI(
        model=model or s.QWEN_MODEL,
        api_key=s.DASHSCOPE_API_KEY,
        base_url=s.DASHSCOPE_BASE_URL,
        temperature=temperature,
        streaming=streaming,
        max_tokens=2048,
        # LangChain 1.x 透传 stream_options，确保流式也能拿到 usage
        model_kwargs={"stream_options": {"include_usage": True}} if streaming else {},
    )


def extract_usage(ai_message) -> dict:
    """
    统一从 AIMessage 中抽取 token 用量
    优先级：usage_metadata > response_metadata.token_usage
    """
    if ai_message is None:
        return {}

    # LangChain 1.x 主推 usage_metadata
    um = getattr(ai_message, "usage_metadata", None)
    if um:
        try:
            return {
                "input_tokens": um.get("input_tokens", 0) if hasattr(um, "get") else getattr(um, "input_tokens", 0),
                "output_tokens": um.get("output_tokens", 0) if hasattr(um, "get") else getattr(um, "output_tokens", 0),
                "total_tokens": um.get("total_tokens", 0) if hasattr(um, "get") else getattr(um, "total_tokens", 0),
            }
        except Exception:
            pass

    # fallback
    rm = getattr(ai_message, "response_metadata", {}) or {}
    tu = rm.get("token_usage") if isinstance(rm, dict) else None
    if tu:
        return {
            "input_tokens": tu.get("prompt_tokens", 0),
            "output_tokens": tu.get("completion_tokens", 0),
            "total_tokens": tu.get("total_tokens", 0),
        }
    return {}
