"""聊天 API - Phase 3 p3-nl2sql + Phase 5 SSE"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.db.database import get_db
from app.services.chat_service import ChatService
from app.services.nl2sql_service import build_nl2sql_agent
from app.services.memory_service import get_session_history
from app.services.session_service import SessionService
from app.services.chart_service import build_chart
from app.schemas.session import ChatRequest, ChatResponse

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"module": "chat", "status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    非流式聊天入口
    - 加载会话历史
    - 调用 NL2SQL Agent
    - 持久化 user + assistant 消息
    - 自动用首条问题更新 session title
    """
    try:
        result = await ChatService.chat(db, payload.session_id, payload.question)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"chat failed: {type(e).__name__}: {e}")


def _sse_event(event: str, data: dict) -> str:
    """构造一个 SSE 事件块"""
    payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    SSE 流式聊天入口

    事件类型：
    - start:        {session_id, question}
    - user_saved:   {user_message_id}
    - tool_call:    {step, name, args}
    - tool_result:  {step, name, content_preview, status}
    - sql:          {sql}
    - chart:        {chart}
    - token:        {delta}              # LLM 流式输出（暂时不可用，因 agent.stream 是 step 级）
    - final:        {assistant_message}  # 完整结果
    - error:        {message}
    - end:          {}
    """
    async def event_gen():
        try:
            # 1. 校验 session
            sess = await SessionService.get_session(db, payload.session_id)
            if not sess:
                yield _sse_event("error", {"message": f"session {payload.session_id} 不存在"})
                yield _sse_event("end", {})
                return

            yield _sse_event("start", {
                "session_id": payload.session_id,
                "question": payload.question,
            })

            # 2. 持久化 user 消息
            user_msg = await SessionService.append_message(
                db, payload.session_id, "user", payload.question
            )
            yield _sse_event("user_saved", {"user_message_id": user_msg.id})

            # 3. 加载历史
            history = await get_session_history(db, payload.session_id).aget_messages()
            ctx_messages = history[:-1] if len(history) > 1 else []
            ctx_messages.append(HumanMessage(content=payload.question))

            # 4. 流式运行 agent
            agent = build_nl2sql_agent(db)
            step_no = 0
            all_tool_calls = []
            last_sql = None
            sql_result = None
            final_ai = None
            usage_acc = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            # langgraph 0.x / langchain 1.x 的 stream 模式：默认 "values"，每步 yield 完整 state
            # 我们用 "updates" 模式拿到每一步的增量
            async for event in agent.astream({"messages": ctx_messages}, stream_mode="updates"):
                # event 是 dict: { node_name: state_delta }
                for node_name, state_delta in event.items():
                    msgs_delta = state_delta.get("messages", [])
                    for m in msgs_delta:
                        step_no += 1
                        if isinstance(m, AIMessage):
                            if m.tool_calls:
                                for tc in m.tool_calls:
                                    tc_dict = {
                                        "name": tc.get("name") if isinstance(tc, dict) else tc.name,
                                        "id": tc.get("id") if isinstance(tc, dict) else tc.id,
                                        "args": tc.get("args") if isinstance(tc, dict) else tc.args,
                                    }
                                    all_tool_calls.append(tc_dict)
                                    if tc_dict["name"] == "sql_db_query" and isinstance(tc_dict["args"], dict):
                                        last_sql = tc_dict["args"].get("query")
                                    yield _sse_event("tool_call", {
                                        "step": step_no,
                                        "name": tc_dict["name"],
                                        "args": tc_dict["args"],
                                    })
                                # 发出 SQL
                                if last_sql:
                                    yield _sse_event("sql", {"sql": last_sql})
                            else:
                                # 最终的 AI 回答
                                final_ai = m
                                if m.content:
                                    yield _sse_event("final_answer", {"content": m.content})
                        elif isinstance(m, ToolMessage):
                            if m.name == "sql_db_query" and m.status == "success":
                                sql_result = m.content
                            yield _sse_event("tool_result", {
                                "step": step_no,
                                "name": m.name,
                                "status": m.status,
                                "content_preview": (m.content or "")[:200],
                            })

                        # 累计 usage
                        um = getattr(m, "usage_metadata", None)
                        if um:
                            if hasattr(um, "get"):
                                usage_acc["input_tokens"] += um.get("input_tokens", 0) or 0
                                usage_acc["output_tokens"] += um.get("output_tokens", 0) or 0
                                usage_acc["total_tokens"] += um.get("total_tokens", 0) or 0

            # ============================================================
            # 守卫（NL2SQL-35 稳定性）：若 LLM 没调过 sql_db_query，强制重试一次
            # ============================================================
            if last_sql is None:
                print("[sse chat] guard: 第一次未调 sql_db_query，强制重试")
                # 收集所有已发出的消息
                all_msgs_so_far = ctx_messages + []
                # 拉取 session 历史以便重试时携带完整上下文
                history = await get_session_history(db, payload.session_id).aget_messages()
                retry_ctx = history[:-1] if len(history) > 1 else []
                retry_ctx.append(HumanMessage(content=payload.question))
                retry_ctx.append(HumanMessage(content="[系统提示] 你的上一次回答没有查询数据库。请重新执行：先调用 sql_db_list_tables，再依次调用 sql_db_schema / sql_db_query_checker / sql_db_query。**必须调用 sql_db_query 才能返回结果。**"))
                yield _sse_event("guard_retry", {"message": "强制重试以确保调用 SQL 工具"})
                async for retry_event in agent.astream({"messages": retry_ctx}, stream_mode="updates"):
                    for node_name, state_delta in retry_event.items():
                        msgs_delta = state_delta.get("messages", [])
                        for m in msgs_delta:
                            step_no += 1
                            if isinstance(m, AIMessage):
                                if m.tool_calls:
                                    for tc in m.tool_calls:
                                        tc_dict = {
                                            "name": tc.get("name") if isinstance(tc, dict) else tc.name,
                                            "id": tc.get("id") if isinstance(tc, dict) else tc.id,
                                            "args": tc.get("args") if isinstance(tc, dict) else tc.args,
                                        }
                                        all_tool_calls.append(tc_dict)
                                        if tc_dict["name"] == "sql_db_query" and isinstance(tc_dict["args"], dict):
                                            last_sql = tc_dict["args"].get("query")
                                        yield _sse_event("tool_call", {
                                            "step": step_no,
                                            "name": tc_dict["name"],
                                            "args": tc_dict["args"],
                                        })
                                    if last_sql:
                                        yield _sse_event("sql", {"sql": last_sql})
                                else:
                                    final_ai = m
                                    if m.content:
                                        yield _sse_event("final_answer", {"content": m.content})
                            elif isinstance(m, ToolMessage):
                                if m.name == "sql_db_query" and m.status == "success":
                                    sql_result = m.content
                                yield _sse_event("tool_result", {
                                    "step": step_no,
                                    "name": m.name,
                                    "status": m.status,
                                    "content_preview": (m.content or "")[:200],
                                })
                            um = getattr(m, "usage_metadata", None)
                            if um and hasattr(um, "get"):
                                usage_acc["input_tokens"] += um.get("input_tokens", 0) or 0
                                usage_acc["output_tokens"] += um.get("output_tokens", 0) or 0
                                usage_acc["total_tokens"] += um.get("total_tokens", 0) or 0

            # 5. 生成 chart
            chart_data = None
            if sql_result and last_sql:
                try:
                    from app.services.nl2sql_service import _parse_sql_tool_output
                    columns, rows = _parse_sql_tool_output(sql_result)
                    if columns and rows:
                        chart_data = build_chart(columns, rows, title=last_sql)
                        yield _sse_event("chart", {"chart": chart_data})
                except Exception as e:
                    yield _sse_event("warning", {"message": f"chart parse failed: {e}"})

            # 6. 持久化 assistant 消息
            answer = final_ai.content if final_ai else "(无回答)"
            meta = {
                "sql": last_sql,
                "chart": chart_data,
                "tool_calls": all_tool_calls,
                "usage": usage_acc,
            }
            ai_msg = await SessionService.append_message(
                db, payload.session_id, "assistant", answer, meta=meta
            )

            # 7. 自动用首条问题更新 session title
            if sess.title == "新会话" and payload.question:
                new_title = payload.question[:30] + ("..." if len(payload.question) > 30 else "")
                await SessionService.rename_session(db, payload.session_id, new_title)
                sess.title = new_title
                yield _sse_event("session_renamed", {"title": new_title})

            # 8. final 事件：把整个 assistant_message 发给前端
            yield _sse_event("final", {
                "session_id": payload.session_id,
                "assistant_message": {
                    "id": ai_msg.id,
                    "session_id": ai_msg.session_id,
                    "role": ai_msg.role,
                    "content": ai_msg.content,
                    "meta": meta,
                    "created_at": ai_msg.created_at.isoformat() if ai_msg.created_at else None,
                },
                "user_message": {
                    "id": user_msg.id,
                    "session_id": user_msg.session_id,
                    "role": user_msg.role,
                    "content": user_msg.content,
                    "meta": {},
                    "created_at": user_msg.created_at.isoformat() if user_msg.created_at else None,
                },
            })
            yield _sse_event("end", {})

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse_event("error", {"message": f"{type(e).__name__}: {e}"})
            yield _sse_event("end", {})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
