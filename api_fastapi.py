from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from decision_engine import DecisionEngine
from evaluation import AgentEvaluator, build_default_evaluation_cases
from llm_strategy_agents import StrategyAgentGenerationError
from logging_config import configure_logging, get_logger
from main import PRESET_SCENES
from memory import DecisionMemory
from models import BattlefieldScene
from planner_evaluation import run_default_planner_evaluation
from rag_evaluation import run_default_rag_evaluation
from schemas import (
    DecisionRecordDetailSchema,
    DecisionRecordSummarySchema,
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    ScenarioMap,
    ToolSpecSchema,
)
from serializers import result_to_dict, scene_to_dict, trace_to_dict
from settings import get_settings
from storage import DecisionRecordStore


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
APP_SETTINGS = get_settings()
DECISION_STORE = DecisionRecordStore(ROOT / APP_SETTINGS.database_path)

configure_logging()
logger = get_logger(__name__)


def _build_decision_engine(llm_mode: str, llm_model: str | None = None) -> DecisionEngine:
    return DecisionEngine(
        llm_mode=llm_mode,
        llm_model=llm_model,
        decision_memory=DecisionMemory(DECISION_STORE),
    )


def _save_decision_and_memory(scene_data: Dict[str, Any], result_data: Dict[str, Any]) -> int:
    record_id = DECISION_STORE.save_decision(scene=scene_data, result=result_data)
    memory_result = DecisionMemory(DECISION_STORE).write_decision(
        record_id=record_id,
        scene=scene_data,
        result=result_data,
    )
    logger.info(
        "Memory write completed: record_id=%s written=%s memory_id=%s importance=%.2f",
        record_id,
        memory_result.written,
        memory_result.memory_id,
        memory_result.importance_score,
    )
    return record_id


def _save_evaluation_report(report_type: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    report_id = DECISION_STORE.save_evaluation_report(report_type=report_type, summary=summary)
    logger.info(
        "Evaluation report saved: report_id=%s type=%s total_cases=%s passed_cases=%s",
        report_id,
        report_type,
        summary.get("total_cases"),
        summary.get("passed_cases"),
    )
    return {"report_id": report_id, **summary}


app = FastAPI(
    title="面向复杂对抗场景的多智能体策略评估系统 API",
    description=(
        "该 API 用于复杂对抗场景下的多智能体策略评估。"
        "系统会根据场景参数生成候选方案，结合动态权重、智能体互评和可选 LLM 裁决增强，"
        "返回最终推荐方案、完整排名、评价权重、互评记录和决策 Trace。"
    ),
    version=APP_SETTINGS.version,
    openapi_tags=[
        {"name": "系统状态", "description": "服务健康检查与基础状态接口"},
        {"name": "场景管理", "description": "预置战场场景查询接口"},
        {"name": "决策评估", "description": "多智能体方案生成、评分、排序与 LLM 增强裁决接口"},
        {"name": "历史记录", "description": "历史决策记录查询接口"},
    ],
)

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return str(value) if value else None


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "HTTP request failed: method=%s path=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            duration_ms,
            request_id,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
    logger.info(
        "HTTP request completed: method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    request_id = _request_id(request)
    if isinstance(detail, dict):
        content = {
            "error": str(detail.get("error", "请求处理失败")),
            "error_type": str(detail.get("error_type", "http_error")),
            "details": detail.get("details"),
            "request_id": request_id,
        }
    else:
        content = {"error": str(detail), "error_type": "http_error", "details": None, "request_id": request_id}
    logger.warning(
        "HTTP error: path=%s status=%s type=%s request_id=%s",
        request.url.path,
        exc.status_code,
        content["error_type"],
        request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _request_id(request)
    logger.warning(
        "Validation error: path=%s errors=%s request_id=%s",
        request.url.path,
        len(exc.errors()),
        request_id,
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "请求参数校验失败",
            "error_type": "validation_error",
            "details": exc.errors(),
            "request_id": request_id,
        },
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def app_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js")


@app.get("/styles.css", include_in_schema=False)
def styles_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "styles.css")


@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["系统状态"],
    summary="健康检查",
    description="检查后端服务是否正常运行，并返回服务名称与版本号。",
)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(ok=True, service=settings.service_name, version=settings.version)


@app.get(
    "/api/scenarios",
    response_model=ScenarioMap,
    tags=["场景管理"],
    summary="获取预置场景列表",
    description=(
        "返回系统内置的战场对抗场景。"
        "前端使用该接口初始化场景下拉框，并将场景参数填入控制面板。"
    ),
)
def list_scenarios() -> Dict[str, Dict[str, Any]]:
    return {key: scene_to_dict(scene) for key, scene in PRESET_SCENES.items()}


@app.get(
    "/api/tools",
    response_model=list[ToolSpecSchema],
    tags=["Agent Tools"],
    summary="查询 Agent 工具目录",
    description="返回当前决策引擎注册的 Agent 工具描述、输入 schema、输出 schema 和标签。",
)
def list_tools() -> list[Dict[str, Any]]:
    engine = _build_decision_engine(llm_mode="off")
    return [spec.to_dict() for spec in engine.tool_registry.specs()]


@app.post(
    "/api/evaluations/run",
    tags=["Agent Evaluation"],
    summary="运行 Agent 默认评估集",
    description=(
        "运行内置 Agent Evaluation 场景集，评估工具计划、Trace 完整性、RAG 证据、"
        "风险分析、审查状态和最终分数。该接口只生成评估报告，不写入历史决策记录。"
    ),
)
def run_evaluation() -> Dict[str, Any]:
    evaluator = AgentEvaluator(lambda: _build_decision_engine(llm_mode="off"))
    summary = evaluator.evaluate(build_default_evaluation_cases())
    return _save_evaluation_report("agent", summary.to_dict())


@app.post(
    "/api/evaluations/planner/run",
    tags=["Agent Evaluation"],
    summary="运行 Agent Planner 默认评估集",
    description="运行 Planner Evaluation，评估工具选择、计划修复次数和修复后的依赖顺序，并保存评估报告。",
)
def run_planner_evaluation() -> Dict[str, Any]:
    summary = run_default_planner_evaluation().to_dict()
    return _save_evaluation_report("planner", summary)


@app.post(
    "/api/evaluations/rag/run",
    tags=["Agent Evaluation"],
    summary="运行 RAG 默认评估集",
    description="运行 RAG Evaluation，评估 hit@k、MRR、nDCG、source match 和 rerank improvement，并保存评估报告。",
)
def run_rag_evaluation() -> Dict[str, Any]:
    summary = run_default_rag_evaluation().to_dict()
    return _save_evaluation_report("rag", summary)


@app.get(
    "/api/evaluations",
    tags=["Agent Evaluation"],
    summary="查询评估报告历史",
    description="按 ID 倒序返回已保存的 Agent、Planner 或 RAG Evaluation 报告摘要。",
)
def list_evaluation_reports(
    report_type: str | None = Query(default=None, description="可选评估类型：agent、planner、rag"),
    limit: int = Query(default=20, ge=1, le=100, description="返回报告数量"),
) -> list[Dict[str, Any]]:
    return [
        item.to_dict()
        for item in DECISION_STORE.list_evaluation_reports(report_type=report_type, limit=limit)
    ]


@app.get(
    "/api/evaluations/{report_id}",
    tags=["Agent Evaluation"],
    summary="查询单条评估报告详情",
    description="根据评估报告 ID 查询完整 Evaluation JSON 报告。",
)
def get_evaluation_report(report_id: int) -> Dict[str, Any]:
    report = DECISION_STORE.get_evaluation_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"评估报告不存在: {report_id}", "error_type": "evaluation_report_not_found"},
        )
    return report.to_dict()


@app.get(
    "/api/memory",
    tags=["Agent Memory"],
    summary="查询 Agent 长期记忆",
    description="返回由历史决策沉淀出的结构化长期记忆条目，包括摘要、经验、标签和重要性分数。",
)
def list_agent_memory(limit: int = Query(default=20, ge=1, le=100, description="返回记忆条目数量")):
    return [entry.to_dict() for entry in DECISION_STORE.list_memory_entries(limit=limit)]


@app.post(
    "/api/decide",
    response_model=DecisionResponse,
    tags=["决策评估"],
    summary="执行多智能体决策评估",
    description=(
        "接收一个战场场景参数对象，调用多个策略智能体生成候选方案，"
        "再根据动态评价权重、智能体互评和可选 LLM 裁决增强计算最终排名。"
        "当 llm_mode 为 off 时仅使用本地规则；auto 会在模型不可用时自动降级；"
        "on 会强制调用模型并在失败时返回错误。"
    ),
)
def decide(request: DecisionRequest) -> Dict[str, Any]:
    logger.info("Decision requested: scene=%s llm_mode=%s", request.scene.name, request.llm_mode)
    try:
        scene = BattlefieldScene(**request.scene.model_dump())
        engine = _build_decision_engine(llm_mode=request.llm_mode, llm_model=request.llm_model)
        result = engine.run(scene)
        result_data = result_to_dict(result)
        scene_data = request.scene.model_dump()
        record_id = _save_decision_and_memory(scene_data=scene_data, result_data=result_data)
        logger.info(
            "Decision completed: scene=%s mode=%s best_agent=%s record_id=%s",
            scene.name,
            result.decision_mode,
            result.best.proposal.agent_name,
            record_id,
        )
        return result_data
    except RuntimeError as exc:
        payload = _runtime_error_payload(exc)
        error_text = payload["error"]
        status = 500
        if payload["error_type"] == "llm_call_failed":
            status = 502
        elif payload["error_type"] == "missing_api_key":
            status = 400
        logger.warning(
            "Decision failed: status=%s type=%s error=%s",
            status,
            payload["error_type"],
            error_text,
        )
        raise HTTPException(status_code=status, detail=payload) from exc


def _sse_event(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _runtime_error_payload(exc: RuntimeError) -> Dict[str, Any]:
    error_text = str(exc)
    error_type = "runtime_error"
    if "外部模型调用失败" in error_text or "strategy agent generation failed" in error_text:
        error_type = "llm_call_failed"
    elif "未检测到 API_KEY" in error_text or "configured model client" in error_text:
        error_type = "missing_api_key"
    details = None
    if isinstance(exc, StrategyAgentGenerationError):
        details = {"failures": [record.to_dict() for record in exc.failures]}
    return {"error": error_text, "error_type": error_type, "details": details}


@app.post(
    "/api/decide/stream",
    tags=["决策评估"],
    summary="流式执行多智能体决策评估",
    description=(
        "以 Server-Sent Events 形式输出决策进度。"
        "阶段事件类型为 progress，最终结果事件类型为 result，结束事件类型为 done。"
    ),
)
def decide_stream(request: DecisionRequest) -> StreamingResponse:
    def generate() -> Iterator[str]:
        logger.info("Streaming decision requested: scene=%s llm_mode=%s", request.scene.name, request.llm_mode)
        try:
            scene = BattlefieldScene(**request.scene.model_dump())
            scene_data = request.scene.model_dump()
            engine = _build_decision_engine(llm_mode=request.llm_mode, llm_model=request.llm_model)
            result_data: Dict[str, Any] | None = None
            record_id: int | None = None

            for progress in engine.run_stream(scene):
                if progress.trace_event is not None:
                    yield _sse_event("progress", trace_to_dict(progress.trace_event))
                if progress.result is not None:
                    result_data = result_to_dict(progress.result)
                    record_id = _save_decision_and_memory(scene_data=scene_data, result_data=result_data)
                    logger.info(
                        "Streaming decision completed: scene=%s mode=%s best_agent=%s record_id=%s",
                        scene.name,
                        progress.result.decision_mode,
                        progress.result.best.proposal.agent_name,
                        record_id,
                    )
                    yield _sse_event("result", {"record_id": record_id, "result": result_data})

            yield _sse_event("done", {"ok": True, "record_id": record_id})
        except RuntimeError as exc:
            payload = _runtime_error_payload(exc)
            logger.warning("Streaming decision failed: type=%s error=%s", payload["error_type"], payload["error"])
            yield _sse_event("error", payload)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get(
    "/api/decisions",
    response_model=list[DecisionRecordSummarySchema],
    tags=["历史记录"],
    summary="查询历史决策记录",
    description="按 ID 倒序返回历史决策摘要列表，可通过 limit 控制返回数量。",
)
def list_decision_records(limit: int = Query(default=20, ge=1, le=100, description="返回记录数量")):
    return DECISION_STORE.list_records(limit=limit)


@app.get(
    "/api/decisions/{record_id}",
    response_model=DecisionRecordDetailSchema,
    tags=["历史记录"],
    summary="查询单条历史决策详情",
    description="根据历史记录 ID 查询完整的场景输入和决策输出。",
)
def get_decision_record(record_id: int):
    record = DECISION_STORE.get_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"历史决策记录不存在: {record_id}", "error_type": "record_not_found"},
        )
    return record
