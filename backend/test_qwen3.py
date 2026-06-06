"""
Qwen3 API 探测脚本
==================
目的：使用真实 API key 探测 qwen3-max 在以下场景的实际返回字段：
  1. 基础 invoke()
  2. 流式输出（stream）
  3. 工具/函数调用（tool_calls）
  4. LangChain ChatOpenAI 封装调用

运行：python test_qwen3.py
"""
import os
import sys
import json
import time
from pprint import pformat

# ====== 配置 ======
API_KEY = "sk-****"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3-max"


def banner(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def dump_obj(obj, indent: int = 0, max_str: int = 600):
    """递归打印对象字段，便于看清返回结构"""
    prefix = "  " * indent
    if obj is None:
        print(f"{prefix}None")
        return
    if isinstance(obj, (str, int, float, bool)):
        s = repr(obj)
        if len(s) > max_str:
            s = s[:max_str] + f"... <truncated {len(s)-max_str} chars>"
        print(f"{prefix}{s}")
        return
    if isinstance(obj, (list, tuple)):
        if not obj:
            print(f"{prefix}[]")
            return
        print(f"{prefix}[")
        for i, item in enumerate(obj[:5]):  # 最多 5 个避免爆炸
            print(f"{prefix}  [{i}]:")
            dump_obj(item, indent + 2, max_str)
        if len(obj) > 5:
            print(f"{prefix}  ... {len(obj) - 5} more")
        print(f"{prefix}]")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            print(f"{prefix}.{k} =")
            dump_obj(v, indent + 1, max_str)
        return
    # Pydantic / 自定义对象
    cls_name = type(obj).__name__
    print(f"{prefix}<{cls_name}>")
    # 尝试取 model_dump 或 dict
    if hasattr(obj, "model_dump"):
        try:
            d = obj.model_dump()
            print(f"{prefix}  model_dump():")
            dump_obj(d, indent + 1, max_str)
            return
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            d = obj.dict()
            print(f"{prefix}  dict():")
            dump_obj(d, indent + 1, max_str)
            return
        except Exception:
            pass
    # 尝试取 __dict__
    if hasattr(obj, "__dict__"):
        d = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        print(f"{prefix}  __dict__:")
        dump_obj(d, indent + 1, max_str)
        return
    print(f"{prefix}{repr(obj)}")


# ============================================================
# 测试 1: 基础调用 (官方 openai SDK)
# ============================================================
def test_1_basic():
    banner("测试 1: 基础 invoke() - openai SDK 原生")
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是一个助手。"},
            {"role": "user", "content": "用一句话介绍你自己。"},
        ],
        temperature=0.2,
    )
    elapsed = time.time() - t0

    print(f"\n[耗时] {elapsed:.2f}s")
    print(f"\n[response 类型] {type(resp).__name__}")
    print(f"\n[完整 response 结构]:")
    dump_obj(resp)

    print(f"\n[response.id] = {resp.id}")
    print(f"[response.model] = {resp.model}")
    print(f"[response.object] = {resp.object}")
    print(f"[response.created] = {resp.created}")
    print(f"\n[choices 长度] = {len(resp.choices)}")
    msg = resp.choices[0].message
    print(f"[choices[0].finish_reason] = {resp.choices[0].finish_reason}")
    print(f"[choices[0].index] = {resp.choices[0].index}")
    print(f"[choices[0].message.role] = {msg.role}")
    print(f"[choices[0].message.content] = {msg.content!r}")
    print(f"[choices[0].message.tool_calls] = {msg.tool_calls}")
    print(f"[choices[0].message.refusal] = {msg.refusal}")

    if resp.usage:
        print(f"\n[usage.prompt_tokens] = {resp.usage.prompt_tokens}")
        print(f"[usage.completion_tokens] = {resp.usage.completion_tokens}")
        print(f"[usage.total_tokens] = {resp.usage.total_tokens}")
        if hasattr(resp.usage, "completion_tokens_details"):
            print(f"[usage.completion_tokens_details] = {resp.usage.completion_tokens_details}")


# ============================================================
# 测试 2: 流式输出
# ============================================================
def test_2_stream():
    banner("测试 2: 流式输出 stream() - openai SDK 原生")
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    t0 = time.time()
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": "用 30 字左右讲一个关于猫的笑话。"},
        ],
        temperature=0.5,
        stream=True,
    )

    print("\n[流式 chunk 列表]:")
    chunks = []
    full_content = ""
    for i, chunk in enumerate(stream):
        chunks.append(chunk)
        # 打印前 3 个和最后 1 个的完整结构
        if i < 3 or i == 0:
            print(f"\n--- chunk[{i}] ---")
            dump_obj(chunk)
        # 拼接内容
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta
            piece = delta.content or ""
            full_content += piece

    elapsed = time.time() - t0
    print(f"\n[总耗时] {elapsed:.2f}s")
    print(f"[chunk 总数] = {len(chunks)}")
    print(f"\n[完整拼接内容] = {full_content!r}")

    # 关键字段检查
    last = chunks[-1]
    print(f"\n[最后一个 chunk.choices[0].finish_reason] = {last.choices[0].finish_reason if last.choices else None}")
    print(f"[最后一个 chunk.usage] = {last.usage}")
    # 注意：流式模式下 usage 字段行为因 provider 而异


# ============================================================
# 测试 3: 工具/函数调用
# ============================================================
def test_3_tool_calls():
    banner("测试 3: 工具/函数调用 tool_calls")
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "查询某个城市的天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_sales",
                "description": "查询销售数据",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "category": {"type": "string"},
                    },
                    "required": ["start_date", "end_date"],
                },
            },
        },
    ]

    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": "帮我查一下北京今天的天气，另外再查一下 2024-12-01 到 2024-12-31 电子产品的销售数据。"},
        ],
        tools=tools,
        tool_choice="auto",
    )
    elapsed = time.time() - t0

    print(f"\n[耗时] {elapsed:.2f}s")
    print(f"\n[response 完整结构]:")
    dump_obj(resp)

    msg = resp.choices[0].message
    print(f"\n[msg.role] = {msg.role}")
    print(f"[msg.content] = {msg.content!r}")
    print(f"[msg.tool_calls] = {msg.tool_calls}")
    print(f"[msg.tool_calls 类型] = {type(msg.tool_calls).__name__}")

    if msg.tool_calls:
        for i, tc in enumerate(msg.tool_calls):
            print(f"\n  tool_call[{i}]:")
            dump_obj(tc, indent=2)
            # 关键字段
            print(f"  -- tc.id = {tc.id}")
            print(f"  -- tc.type = {tc.type}")
            print(f"  -- tc.function.name = {tc.function.name}")
            print(f"  -- tc.function.arguments = {tc.function.arguments!r}")

        # 模拟把工具结果回传，让 LLM 继续生成
        tool_messages = []
        for tc in msg.tool_calls:
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps({"temperature": 18, "unit": "celsius", "condition": "晴"})
                if tc.function.name == "get_weather"
                else json.dumps({"total_sales": 1250000, "orders": 320}),
            })
        messages2 = [
            {"role": "user", "content": "帮我查一下北京今天的天气，另外再查一下 2024-12-01 到 2024-12-31 电子产品的销售数据。"},
            msg,
            *tool_messages,
        ]
        print(f"\n[把工具结果回传后继续生成]:")
        resp2 = client.chat.completions.create(
            model=MODEL,
            messages=messages2,
            tools=tools,
        )
        print(f"  final content = {resp2.choices[0].message.content!r}")


# ============================================================
# 测试 4: LangChain ChatOpenAI 封装
# ============================================================
def test_4_langchain():
    banner("测试 4: LangChain ChatOpenAI 封装")
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.3,
        max_tokens=512,
    )

    # 4.1 基础 invoke
    print("\n--- 4.1 ChatOpenAI.invoke() ---")
    t0 = time.time()
    result = llm.invoke([
        SystemMessage(content="你是一个简短的助手。"),
        HumanMessage(content="1+1 等于几？"),
    ])
    elapsed = time.time() - t0
    print(f"[耗时] {elapsed:.2f}s")
    print(f"\n[AIMessage 完整结构]:")
    dump_obj(result)
    print(f"\n[result.content] = {result.content!r}")
    print(f"[result.type] = {result.type}")
    print(f"[result.response_metadata] = {result.response_metadata}")
    print(f"[result.usage_metadata] = {result.usage_metadata}")
    print(f"[result.id] = {result.id}")
    print(f"[result.tool_calls] = {result.tool_calls}")
    print(f"[result.additional_kwargs] = {result.additional_kwargs}")

    # 4.2 LangChain 流式
    print("\n--- 4.2 ChatOpenAI.stream() ---")
    t0 = time.time()
    chunks = []
    for chunk in llm.stream([HumanMessage(content="用 20 字介绍北京。")]):
        chunks.append(chunk)
        # 打印前 2 个
        if len(chunks) <= 2:
            print(f"\n  chunk[{len(chunks)-1}]:")
            dump_obj(chunk, indent=1)
    elapsed = time.time() - t0
    print(f"\n[总耗时] {elapsed:.2f}s")
    print(f"[chunks 总数] = {len(chunks)}")
    full = "".join(c.content for c in chunks if isinstance(c.content, str))
    print(f"[拼接后完整内容] = {full!r}")
    if chunks:
        print(f"[最后一个 chunk.response_metadata] = {chunks[-1].response_metadata}")


# ============================================================
def main():
    print(f"[*] API key 前 6 位: {API_KEY[:6]}***")
    print(f"[*] Base URL: {BASE_URL}")
    print(f"[*] Model: {MODEL}")

    only = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        if only in (None, "1"):
            test_1_basic()
        if only in (None, "2"):
            test_2_stream()
        if only in (None, "3"):
            test_3_tool_calls()
        if only in (None, "4"):
            test_4_langchain()
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 70)
    print("  全部测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
