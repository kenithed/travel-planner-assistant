"""AI 行程问答路由"""

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from ...models.schemas import TripChatRequest, TripChatResponse
from ...models.trip_edit import TripEditApplyRequest
from ...services.chat_service import chat_with_trip_context
from ...services.nearby_search import NearbySearchError
from ...services.trip_edit_service import prepare_edit, apply_edit

router = APIRouter(prefix="/chat", tags=["AI问答"])


@router.post(
    "/ask",
    response_model=TripChatResponse,
    summary="行程智能问答",
    description="根据当前旅行计划上下文,回答用户关于行程的问题"
)
async def ask_about_trip(request: TripChatRequest):
    """
    AI 行程问答

    Args:
        request: 包含用户提问、旅行计划上下文和历史对话

    Returns:
        AI 回复
    """
    try:
        if request.mode != "ask":
            try:
                result = await prepare_edit(request)
                return TripChatResponse(success=True, **result)
            except NearbySearchError as error:
                return TripChatResponse(success=True, kind="clarify", reply=str(error))
            except TimeoutError:
                return TripChatResponse(success=True, kind="error", reply="附近搜索超时，请稍后重试。原行程没有变化。")
            except ValidationError:
                raise HTTPException(status_code=422, detail="当前行程数据不完整，无法执行局部修改。") from None
        print(f"\n💬 收到行程问答: {request.message[:50]}...")

        # 将 history 转换为 dict 列表
        history = [{"role": m.role, "content": m.content} for m in (request.history or [])]

        reply = await chat_with_trip_context(
            message=request.message,
            trip_plan_dict=request.trip_plan,
            history=history,
        )

        print(f"✅ AI 回复: {reply[:80]}...")

        return TripChatResponse(
            success=True,
            reply=reply,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 行程问答失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="AI 服务暂时不可用，请稍后重试。原行程没有变化。"
        )


@router.post("/edit/apply", summary="确认单个景点替换")
async def confirm_trip_edit(request: TripEditApplyRequest):
    try:
        return apply_edit(request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
