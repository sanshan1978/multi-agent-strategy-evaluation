const metricLabels = {
  success_prob: "成功率",
  resource_efficiency: "资源效率",
  risk_control: "风险控制",
  response_speed: "响应速度",
  intel_alignment: "情报匹配",
};

const sliderDefs = [
  ["enemy_strength", "敌方强度"],
  ["own_strength", "我方强度"],
  ["supply_level", "补给水平"],
  ["intel_quality", "情报质量"],
  ["urgency", "时效压力"],
  ["civilian_presence", "平民密度"],
];

let scenarios = {};
let scene = null;
let selectedAgent = "";
let backendResult = null;
let historyRecords = [];
let selectedHistoryId = null;
let streamingTrace = [];

const $ = (selector) => document.querySelector(selector);

function clamp(value, low = 0, high = 100) {
  return Math.max(low, Math.min(high, value));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

async function initialize() {
  try {
    setBackendStatus("正在加载后端场景配置...", "");
    await loadScenarios();
    initControls();
    syncControls();
    await loadHistoryRecords();
    invalidateBackendResult("当前还没有决策结果，请先运行 Python 决策。");
    render();
  } catch (error) {
    setBackendStatus(`后端初始化失败：${error.message}`, "error");
    renderDisconnectedState(error.message);
  }
}

async function loadHistoryRecords() {
  const response = await fetch("/api/decisions?limit=20");
  if (!response.ok) {
    historyRecords = [];
    return;
  }
  const data = await response.json();
  historyRecords = Array.isArray(data) ? data : [];
}

async function loadScenarios() {
  const response = await fetch("/api/scenarios");
  if (!response.ok) {
    throw new Error(`API 请求失败: HTTP ${response.status}`);
  }
  const data = await response.json();
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("无法读取场景列表，返回格式异常");
  }
  const scenarioKeys = Object.keys(data);
  if (!scenarioKeys.length) {
    throw new Error("后端没有可用场景");
  }
  scenarios = data;
  scene = clone(scenarios[scenarioKeys[0]]);
}

function initControls() {
  const scenarioSelect = $("#scenarioSelect");
  scenarioSelect.innerHTML = Object.entries(scenarios)
    .map(([key, value]) => `<option value="${key}">${value.name}</option>`)
    .join("");

  const sliders = $("#sliders");
  sliders.innerHTML = "";
  sliderDefs.forEach(([key, label]) => {
    const row = document.createElement("div");
    row.className = "slider-row";
    row.innerHTML = `
      <div class="slider-head">
        <strong>${label}</strong>
        <span id="${key}Value"></span>
      </div>
      <input id="${key}Input" type="range" min="0" max="100" step="1" />
    `;
    sliders.appendChild(row);
  });

  scenarioSelect.addEventListener("change", (event) => {
    scene = clone(scenarios[event.target.value]);
    selectedAgent = "";
    syncControls();
    invalidateBackendResult("场景已切换，请重新运行 Python 决策。");
    render();
  });

  $("#objectiveText").addEventListener("input", (event) => {
    scene.objective = event.target.value;
    invalidateBackendResult("任务目标已修改，请重新运行 Python 决策。");
    render();
  });

  $("#terrainSelect").addEventListener("change", (event) => {
    scene.terrain = event.target.value;
    invalidateBackendResult("地形已修改，请重新运行 Python 决策。");
    render();
  });

  $("#weatherInput").addEventListener("input", (event) => {
    scene.weather = event.target.value;
    invalidateBackendResult("天气已修改，请重新运行 Python 决策。");
    render();
  });

  sliderDefs.forEach(([key]) => {
    $(`#${key}Input`).addEventListener("input", (event) => {
      scene[key] = Number(event.target.value);
      $(`#${key}Value`).textContent = scene[key];
      invalidateBackendResult("场景参数已修改，请重新运行 Python 决策。");
      render();
    });
  });

  $("#backendBtn").addEventListener("click", () => requestBackendDecision());
  $("#refreshHistoryBtn").addEventListener("click", () => refreshHistoryRecords());

  $("#resetBtn").addEventListener("click", () => {
    const key = $("#scenarioSelect").value;
    scene = clone(scenarios[key]);
    selectedAgent = "";
    syncControls();
    invalidateBackendResult("场景已重置，请重新运行 Python 决策。");
    render();
  });
}

async function refreshHistoryRecords() {
  const button = $("#refreshHistoryBtn");
  button.disabled = true;
  try {
    await loadHistoryRecords();
    renderHistory();
  } finally {
    button.disabled = false;
  }
}

function syncControls() {
  if (!scene) return;
  const activeKey =
    Object.entries(scenarios).find(([, value]) => value.name === scene.name)?.[0] || Object.keys(scenarios)[0];
  $("#scenarioSelect").value = activeKey;
  $("#objectiveText").value = scene.objective;
  $("#terrainSelect").value = scene.terrain;
  $("#weatherInput").value = scene.weather;
  sliderDefs.forEach(([key]) => {
    $(`#${key}Input`).value = scene[key];
    $(`#${key}Value`).textContent = scene[key];
  });
}

function invalidateBackendResult(message) {
  backendResult = null;
  setBackendStatus(message, "");
}

function setBackendStatus(text, state = "") {
  const node = $("#backendStatus");
  node.textContent = text;
  node.className = `backend-status ${state}`.trim();
}

async function requestBackendDecision() {
  const button = $("#backendBtn");
  button.disabled = true;
  streamingTrace = [];
  backendResult = null;
  selectedHistoryId = null;
  renderEmptyState();
  renderTrace(streamingTrace);
  setBackendStatus("正在流式执行 Python 后端决策...", "");

  try {
    const response = await fetch("/api/decide/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scene,
        llm_mode: $("#llmModeSelect").value,
      }),
    });
    if (!response.body) {
      await requestBackendDecisionFallback();
      return;
    }
    await consumeDecisionStream(response);
  } catch (error) {
    backendResult = null;
    setBackendStatus(buildBackendErrorMessage(error), "error");
    render();
  } finally {
    button.disabled = false;
  }
}

async function loadHistoryDetail(recordId) {
  try {
    const response = await fetch(`/api/decisions/${recordId}`);
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    selectedHistoryId = recordId;
    scene = clone(data.scene);
    backendResult = data.result;
    selectedAgent = backendResult.best?.proposal?.agent_name || "";
    syncControls();
    setBackendStatus(`已载入历史记录 #${recordId}：${formatDecisionMode(backendResult.decision_mode)}`, "ok");
    render();
  } catch (error) {
    setBackendStatus(`历史记录加载失败：${error.message}`, "error");
  }
}

async function requestBackendDecisionFallback() {
  const response = await fetch("/api/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scene,
      llm_mode: $("#llmModeSelect").value,
    }),
  });
  const data = await response.json();
  if (!response.ok || data.error) {
    const err = new Error(data.error || `HTTP ${response.status}`);
    err.errorType = data.error_type || "";
    throw err;
  }
  backendResult = data;
  selectedAgent = data.best?.proposal?.agent_name || "";
  await loadHistoryRecords();
  setBackendStatus(`后端决策完成：${formatDecisionMode(data.decision_mode)}`, "ok");
  render();
}

async function consumeDecisionStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      await handleDecisionStreamEvent(parseSseBlock(part));
    }
  }

  if (buffer.trim()) {
    await handleDecisionStreamEvent(parseSseBlock(buffer));
  }
}

function parseSseBlock(block) {
  const lines = block.split(/\r?\n/);
  let event = "message";
  const dataLines = [];
  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  });
  return {
    event,
    data: dataLines.length ? JSON.parse(dataLines.join("\n")) : {},
  };
}

async function handleDecisionStreamEvent(payload) {
  if (!payload) return;
  if (payload.event === "progress") {
    streamingTrace.push(payload.data);
    renderTrace(streamingTrace);
    setBackendStatus(`决策进行中：${payload.data.message}`, "");
    return;
  }
  if (payload.event === "result") {
    backendResult = payload.data.result;
    selectedAgent = backendResult.best?.proposal?.agent_name || "";
    selectedHistoryId = payload.data.record_id || null;
    await loadHistoryRecords();
    setBackendStatus(`后端决策完成：${formatDecisionMode(backendResult.decision_mode)}`, "ok");
    render();
    return;
  }
  if (payload.event === "error") {
    const err = new Error(payload.data.error || "流式决策失败");
    err.errorType = payload.data.error_type || "";
    throw err;
  }
}

function buildBackendErrorMessage(error) {
  if (error.errorType === "llm_call_failed" || error.message.includes("外部模型调用失败")) {
    return `模型调用失败：${error.message}。服务已连通；可将 LLM 模式切到 auto 自动回退，或切到 off 仅使用规则决策。`;
  }
  if (error.errorType === "missing_api_key" || error.message.includes("API_KEY")) {
    return `缺少模型密钥：${error.message}。请在启动 api_server.py 的终端里配置 API_KEY 或 OPENAI_API_KEY。`;
  }
  return `后端服务不可用：${error.message}。请确认 python api_server.py 正在运行。`;
}

function render() {
  if (!scene) {
    renderDisconnectedState("未加载到场景");
    return;
  }

  if (!backendResult) {
    renderEmptyState();
    return;
  }

  const result = backendResult;
  if (!selectedAgent || !result.ranking.some((item) => item.proposal.agent_name === selectedAgent)) {
    selectedAgent = result.best.proposal.agent_name;
  }

  $("#sceneName").textContent = `${scene.name} / ${scene.terrain} / ${scene.weather}`;
  $("#bestStrategy").textContent = `${result.best.proposal.agent_name}: ${result.best.proposal.strategy_name}`;
  $("#bestReason").textContent = result.llm_reason || result.best.proposal.rationale;
  $("#decisionMode").textContent = formatDecisionMode(result.decision_mode);
  $("#runtimeMode").textContent = "Python 后端结果";

  renderStatusGrid(result);
  renderSummary(result);
  renderRanking(result);
  renderDetail(result);
  renderWeights(result.weights);
  renderKnowledge(result.knowledge_context || []);
  renderMemory(result.memory_context || []);
  renderToolPlan(result.tool_plan || null);
  renderToolCalls(result.tool_calls || [], result.tool_metrics || null);
  renderMessages(result.messages);
  renderTrace(result.trace || []);
  renderHistory();
}

function renderEmptyState() {
  $("#runtimeMode").textContent = "等待后端运行";
  $("#sceneName").textContent = scene ? `${scene.name} / ${scene.terrain} / ${scene.weather}` : "未加载场景";
  $("#bestStrategy").textContent = "尚未生成决策结果";
  $("#bestReason").textContent = "当前页面不再使用前端本地模拟结果。修改场景参数后，请点击 [运行 Python 决策] 获取真实后端返回。";
  $("#decisionMode").textContent = "待运行";

  $("#statusGrid").innerHTML = [
    ["结果来源", "后端真实计算"],
    ["当前状态", "等待运行"],
    ["参数状态", "可编辑"],
    ["LLM状态", "未请求"],
  ]
    .map(([label, value]) => `<div class="status-cell"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  $("#summaryStrip").innerHTML = [
    ["当前推荐", "--"],
    ["综合分", "--"],
    ["兵力比", scene ? (scene.own_strength / Math.max(scene.enemy_strength, 1)).toFixed(2) : "--"],
    ["优先指标", "--"],
  ]
    .map(([label, value]) => `<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  $("#rankingList").innerHTML = `<div class="empty-panel">运行后端决策后，这里才会展示真实方案排名。</div>`;
  $("#detailView").innerHTML = `<div class="empty-panel">选择并运行场景后，这里显示方案详情。</div>`;
  $("#weightBars").innerHTML = `<div class="empty-panel">动态权重由后端决策结果返回。</div>`;
  $("#knowledgeList").innerHTML = `<div class="empty-panel">RAG 知识片段将在后端决策完成后展示。</div>`;
  $("#memoryList").innerHTML = `<div class="empty-panel">Agent Memory 会在后端决策完成后展示相似历史案例。</div>`;
  $("#toolPlanList").innerHTML = `<div class="empty-panel">Agent 工具规划将在后端决策完成后展示。</div>`;
  $("#toolCallList").innerHTML = `<div class="empty-panel">Agent 工具调用轨迹将在后端决策完成后展示。</div>`;
  $("#messageLog").innerHTML = `<div class="empty-panel">智能体交流结果将在后端决策完成后展示。</div>`;
  $("#traceTimeline").innerHTML = `<div class="empty-panel">运行后端决策后，这里会展示完整决策流程。</div>`;
  renderHistory();
}

function renderDisconnectedState(message) {
  $("#runtimeMode").textContent = "后端未连接";
  $("#sceneName").textContent = "后端初始化失败";
  $("#bestStrategy").textContent = "无法加载页面核心数据";
  $("#bestReason").textContent = message;
  $("#decisionMode").textContent = "不可用";
  $("#statusGrid").innerHTML = `<div class="status-cell"><span>错误</span><strong>${message}</strong></div>`;
  $("#summaryStrip").innerHTML = `<div class="summary-card"><span>状态</span><strong>后端不可用</strong></div>`;
  $("#rankingList").innerHTML = `<div class="empty-panel">后端不可用，无法展示排名。</div>`;
  $("#detailView").innerHTML = `<div class="empty-panel">后端不可用，无法展示详情。</div>`;
  $("#weightBars").innerHTML = `<div class="empty-panel">后端不可用，无法展示权重。</div>`;
  $("#knowledgeList").innerHTML = `<div class="empty-panel">后端不可用，无法展示 RAG 知识上下文。</div>`;
  $("#memoryList").innerHTML = `<div class="empty-panel">后端不可用，无法展示 Agent Memory。</div>`;
  $("#toolPlanList").innerHTML = `<div class="empty-panel">后端不可用，无法展示 Agent 工具规划。</div>`;
  $("#toolCallList").innerHTML = `<div class="empty-panel">后端不可用，无法展示 Agent 工具调用。</div>`;
  $("#messageLog").innerHTML = `<div class="empty-panel">后端不可用，无法展示交流结果。</div>`;
  $("#traceTimeline").innerHTML = `<div class="empty-panel">后端不可用，无法展示决策 Trace。</div>`;
  $("#historyList").innerHTML = `<div class="empty-panel">后端不可用，无法读取历史记录。</div>`;
}

function formatDecisionMode(mode) {
  if (!mode) return "待运行";
  if (mode.startsWith("llm+rules")) return "模型增强决策";
  if (mode.includes("no-api-key")) return "规则决策 / 未配置密钥";
  if (mode.includes("llm-failed")) return "规则决策 / 模型回退";
  if (mode === "local-rules") return "规则决策";
  return mode;
}

function renderSummary(result) {
  const best = result.best.proposal;
  const ratio = scene.own_strength / Math.max(scene.enemy_strength, 1);
  const topMetric = Object.entries(best.metric_scores).sort((a, b) => Number(b[1]) - Number(a[1]))[0]?.[0] || "";
  const items = [
    ["当前推荐", best.strategy_name],
    ["综合分", result.best.finalScore.toFixed(2)],
    ["兵力比", ratio.toFixed(2)],
    ["优势指标", metricLabels[topMetric] || "--"],
  ];

  $("#summaryStrip").innerHTML = items
    .map(([label, value]) => `<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderStatusGrid(result) {
  const best = result.best.proposal;
  const ratio = scene.own_strength / Math.max(scene.enemy_strength, 1);
  const items = [
    ["决策模式", formatDecisionMode(result.decision_mode)],
    ["推荐智能体", best.agent_name],
    ["兵力比", ratio.toFixed(2)],
    ["LLM推荐", result.llm_recommended_agent || "未返回"],
  ];

  $("#statusGrid").innerHTML = items
    .map(([label, value]) => `<div class="status-cell"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderRanking(result) {
  $("#rankingList").innerHTML = result.ranking
    .map((item, index) => {
      const proposal = item.proposal;
      const active = proposal.agent_name === selectedAgent ? " active" : "";
      const metrics = normalizedScores(proposal.metric_scores);
      const firstMetric = Object.entries(metrics)[0];
      return `
        <article class="rank-item${active}" data-agent="${proposal.agent_name}">
          <div class="rank-topline">
            <div class="rank-name">${index + 1}. ${proposal.agent_name}</div>
            <div class="score-badge">${item.finalScore.toFixed(1)}</div>
          </div>
          <div class="rank-summary">${proposal.strategy_name} / ${proposal.summary}</div>
          <div class="metric-mini">
            <small>${metricLabels[firstMetric[0]]}: ${firstMetric[1].toFixed(0)}</small>
            <div class="mini-bar"><span style="width: ${firstMetric[1]}%"></span></div>
          </div>
        </article>
      `;
    })
    .join("");

  document.querySelectorAll(".rank-item").forEach((node) => {
    node.addEventListener("click", () => {
      selectedAgent = node.dataset.agent;
      render();
    });
  });
}

function renderDetail(result) {
  const item = result.ranking.find((entry) => entry.proposal.agent_name === selectedAgent) ?? result.best;
  const proposal = item.proposal;
  $("#selectedScore").textContent = `综合分 ${item.finalScore.toFixed(2)}`;
  const llmBonus = Number(item.llmBonus || 0);
  const detailTags = [
    `置信度 ${Number(proposal.confidence || 0).toFixed(2)}`,
    `互评支持 ${Number(proposal.peer_support || 0).toFixed(2)}`,
    `LLM加分 ${llmBonus >= 0 ? "+" : ""}${llmBonus.toFixed(2)}`,
  ];

  const metricHtml = Object.entries(normalizedScores(proposal.metric_scores))
    .map(
      ([key, value]) => `
        <div class="metric-cell">
          <span>${metricLabels[key]}</span>
          <strong>${value.toFixed(1)}</strong>
        </div>
      `
    )
    .join("");

  $("#detailView").innerHTML = `
    <h3>${proposal.strategy_name}</h3>
    <div class="detail-meta">
      ${detailTags.map((tag) => `<span class="detail-tag">${tag}</span>`).join("")}
    </div>
    <div class="detail-summary">${proposal.summary}</div>
    <p>${proposal.rationale}</p>
    <div class="metric-grid">${metricHtml}</div>
    <ul class="action-list">
      ${proposal.actions.map((action) => `<li>${action}</li>`).join("")}
    </ul>
  `;
}

function renderWeights(weights) {
  $("#weightBars").innerHTML = Object.entries(weights)
    .map(
      ([key, value]) => `
        <div class="weight-row">
          <div class="weight-label">
            <span>${metricLabels[key]}</span>
            <strong>${(value * 100).toFixed(2)}%</strong>
          </div>
          <div class="weight-track"><span class="weight-fill" style="width: ${value * 100}%"></span></div>
        </div>
      `
    )
    .join("");
}

function renderKnowledge(snippets) {
  if (!snippets.length) {
    $("#knowledgeList").innerHTML = `<div class="empty-panel">本次决策没有召回 RAG 知识片段。</div>`;
    return;
  }

  $("#knowledgeList").innerHTML = snippets
    .map(
      (item) => `
        <article class="knowledge-item">
          <strong>${escapeHtml(item.title)}</strong>
          <div class="knowledge-meta">
            <span>${escapeHtml(item.source)}</span>
            <span>score ${Number(item.score || 0).toFixed(2)}</span>
          </div>
          <p>${escapeHtml(item.content)}</p>
        </article>
      `
    )
    .join("");
}

function renderMemory(cases) {
  if (!cases.length) {
    $("#memoryList").innerHTML = `<div class="empty-panel">本次决策没有召回相似历史案例。</div>`;
    return;
  }

  $("#memoryList").innerHTML = cases
    .map((item) => {
      const features = Array.isArray(item.matched_features) ? item.matched_features.join(", ") : "--";
      return `
        <article class="memory-item">
          <div class="rank-topline">
            <strong>#${Number(item.record_id)} ${escapeHtml(item.scene_name)}</strong>
            <span class="memory-score">${(Number(item.similarity || 0) * 100).toFixed(0)}%</span>
          </div>
          <p>${escapeHtml(item.best_agent)} / ${escapeHtml(item.best_strategy)}</p>
          <div class="knowledge-meta">
            <span>${escapeHtml(item.decision_mode)}</span>
            <span>${escapeHtml(features)}</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderToolPlan(toolPlan) {
  if (!toolPlan || !Array.isArray(toolPlan.steps) || !toolPlan.steps.length) {
    $("#toolPlanList").innerHTML = `<div class="empty-panel">本次决策没有工具规划记录。</div>`;
    return;
  }

  const steps = toolPlan.steps
    .map(
      (step) => `
        <article class="tool-plan-item">
          <div class="rank-topline">
            <strong>${Number(step.sequence)}. ${escapeHtml(step.tool_name)}</strong>
            <span>${escapeHtml(step.required ? "required" : "optional")}</span>
          </div>
          <p>${escapeHtml(step.purpose)}</p>
          <div class="knowledge-meta">
            <span>${escapeHtml(formatMetadataValue(step.parameters || {}))}</span>
          </div>
        </article>
      `
    )
    .join("");

  $("#toolPlanList").innerHTML = `
    <div class="tool-plan-head">
      <strong>${escapeHtml(toolPlan.strategy)}</strong>
      <span>${toolPlan.steps.length} steps</span>
    </div>
    ${steps}
  `;
}

function renderToolCalls(toolCalls, toolMetrics = null) {
  if (!toolCalls.length) {
    $("#toolCallList").innerHTML = `<div class="empty-panel">本次决策没有工具调用记录。</div>`;
    return;
  }

  const metricSummary = toolMetrics
    ? `
      <div class="tool-metrics">
        <span>total ${Number(toolMetrics.total || 0)}</span>
        <span>failed ${Number(toolMetrics.failed || 0)}</span>
        <span>fallback ${Number(toolMetrics.fallback_used || 0)}</span>
        <span>${Number(toolMetrics.total_duration_ms || 0).toFixed(1)}ms</span>
      </div>
    `
    : "";

  $("#toolCallList").innerHTML = metricSummary + toolCalls
    .map((item) => {
      const metadata = Object.entries(item.metadata || {})
        .slice(0, 3)
        .map(([key, value]) => `<span>${escapeHtml(key)}: ${escapeHtml(formatMetadataValue(value))}</span>`)
        .join("");
      return `
        <article class="tool-call-item">
          <div class="rank-topline">
            <strong>${escapeHtml(item.tool_name)}</strong>
            <span class="memory-score">${Number(item.duration_ms || 0).toFixed(1)}ms</span>
          </div>
          <p>${escapeHtml(item.status)}</p>
          <div class="knowledge-meta">${metadata}</div>
        </article>
      `;
    })
    .join("");
}

function formatMetadataValue(value) {
  if (Array.isArray(value)) return `${value.length} items`;
  if (value && typeof value === "object") return JSON.stringify(value);
  return value ?? "--";
}

function renderMessages(messages) {
  $("#messageLog").innerHTML = messages
    .slice(0, 10)
    .map(
      (message) => `
        <div class="message">
          <strong>${message.from_agent} -> ${message.to_agent} (${message.impact >= 0 ? "+" : ""}${message.impact.toFixed(2)})</strong>
          <span>${message.content}</span>
        </div>
      `
    )
    .join("");
}

function renderTrace(trace) {
  if (!trace.length) {
    $("#traceTimeline").innerHTML = `<div class="empty-panel">当前结果没有 Trace 记录。</div>`;
    return;
  }

  $("#traceTimeline").innerHTML = trace
    .map((event, index) => {
      const statusClass = event.status === "failed" ? " failed" : event.status === "skipped" ? " skipped" : "";
      const metadata = event.metadata && Object.keys(event.metadata).length
        ? `<pre>${escapeHtml(JSON.stringify(event.metadata, null, 2))}</pre>`
        : "";
      return `
        <article class="trace-item${statusClass}">
          <div class="trace-marker">${index + 1}</div>
          <div class="trace-body">
            <div class="trace-head">
              <strong>${escapeHtml(event.step)}</strong>
              <span>${escapeHtml(event.status)}</span>
            </div>
            <p>${escapeHtml(event.message)}</p>
            <small>${formatDateTime(event.timestamp)}</small>
            ${metadata}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderHistory() {
  if (!historyRecords.length) {
    $("#historyList").innerHTML = `<div class="empty-panel">暂无历史记录。运行一次决策后会自动保存。</div>`;
    return;
  }

  $("#historyList").innerHTML = historyRecords
    .map((record) => {
      const active = Number(record.id) === Number(selectedHistoryId) ? " active" : "";
      return `
        <article class="history-item${active}" data-record-id="${record.id}">
          <div class="history-topline">
            <strong>#${record.id} ${escapeHtml(record.scene_name)}</strong>
            <span>${formatDecisionMode(record.decision_mode)}</span>
          </div>
          <p>${escapeHtml(record.best_agent)} / ${escapeHtml(record.best_strategy)}</p>
          <small>${formatDateTime(record.created_at)}</small>
        </article>
      `;
    })
    .join("");

  document.querySelectorAll(".history-item").forEach((node) => {
    node.addEventListener("click", () => {
      loadHistoryDetail(Number(node.dataset.recordId));
    });
  });
}

function normalizedScores(metricScores) {
  return Object.fromEntries(Object.entries(metricScores).map(([key, value]) => [key, clamp(Number(value || 0))]));
}

window.addEventListener("resize", () => render());
initialize();
