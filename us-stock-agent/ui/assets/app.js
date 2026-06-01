const PROMPTS = [
  ["시장", "오늘 미국장 체크포인트 정리해줘", "newspaper"],
  ["섹터", "장중 섹터 강약 정리해줘", "activity"],
  ["기술", "NVDA technical rsi macd setup", "line-chart"],
  ["옵션", "NVDA options flow call wall put wall max pain", "layers-3"],
  ["공시", "NVDA SEC filings 10-Q 8-K 확인해줘", "file-search"],
  ["비교", "NVDA vs AMD 뭐 먼저 볼까", "git-compare"]
];

const TEMPLATES = [
  { label: "시장 브리프", request: "오늘 미국장 체크포인트 정리해줘" },
  { label: "NVDA 기술", request: "NVDA technical rsi macd setup" },
  { label: "섹터 강약", request: "장중 섹터 강약 정리해줘" },
  { label: "옵션 플로우", request: "NVDA options flow call wall put wall max pain" },
  { label: "SEC 공시", request: "NVDA SEC filings 10-Q 8-K 확인해줘" }
];

const state = {
  response: null,
  history: loadHistory(),
  messages: [],
  modelSettings: loadModelSettings()
};

const $ = (selector) => document.querySelector(selector);

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function loadHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem("us-stock-agent-history") || "[]");
    return Array.isArray(parsed) ? parsed.slice(0, 8) : [];
  } catch {
    return [];
  }
}

function saveHistory(item) {
  const normalized = { request: item.request || "" };
  state.history = [
    normalized,
    ...state.history.filter((row) => row.request !== normalized.request)
  ].slice(0, 8);
  localStorage.setItem("us-stock-agent-history", JSON.stringify(state.history));
  renderHistory();
}

function loadModelSettings() {
  try {
    const parsed = JSON.parse(localStorage.getItem("us-stock-agent-model-settings") || "{}");
    const model = typeof parsed.model === "string" ? parsed.model : "";
    const reasoning = ["low", "medium", "high", "xhigh"].includes(parsed.reasoning) ? parsed.reasoning : "";
    return { model, reasoning };
  } catch {
    return { model: "", reasoning: "" };
  }
}

function saveModelSettings() {
  state.modelSettings = {
    model: $("#modelInput").value.trim(),
    reasoning: $("#reasoningLevel").value || ""
  };
  localStorage.setItem("us-stock-agent-model-settings", JSON.stringify(state.modelSettings));
  renderModelStatus();
}

function renderModelStatus(response = null) {
  const model = response?.model || state.modelSettings.model || "OMX 기본 모델";
  const reasoning = response?.reasoning_effort || state.modelSettings.reasoning || "OMX 기본 추론";
  $("#topMeta").textContent = `${model} · ${reasoning}`;
}

function setupModelControls() {
  $("#modelInput").value = state.modelSettings.model;
  $("#reasoningLevel").value = state.modelSettings.reasoning;
  $("#modelInput").addEventListener("change", saveModelSettings);
  $("#modelInput").addEventListener("blur", saveModelSettings);
  $("#reasoningLevel").addEventListener("change", saveModelSettings);
  renderModelStatus();
}

function renderPrompts() {
  const quick = $("#quickModes");
  quick.innerHTML = "";
  PROMPTS.forEach(([label, request, icon]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-mode";
    button.innerHTML = `<i data-lucide="${icon}"></i><span>${label}</span>`;
    button.addEventListener("click", () => {
      $("#requestInput").value = request;
      $("#requestInput").focus();
    });
    quick.appendChild(button);
  });
  initIcons();
}

function renderTemplates() {
  const row = $("#templateRow");
  row.innerHTML = "";
  TEMPLATES.forEach((template) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "template-button";
    button.textContent = template.label;
    button.addEventListener("click", () => {
      $("#requestInput").value = template.request;
      $("#requestInput").focus();
    });
    row.appendChild(button);
  });
}

function renderWatchlist(symbols) {
  const target = $("#watchlistChips");
  target.innerHTML = "";
  symbols.slice(0, 40).forEach((symbol) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = symbol;
    chip.addEventListener("click", () => {
      const input = $("#requestInput");
      const current = input.value.trim();
      input.value = current ? `${current} ${symbol}` : `${symbol} 체크해줘`;
      input.focus();
    });
    target.appendChild(chip);
  });
}

function renderHistory() {
  const list = $("#historyList");
  list.innerHTML = "";
  if (!state.history.length) {
    const empty = document.createElement("div");
    empty.className = "empty-line";
    empty.textContent = "없음";
    list.appendChild(empty);
    return;
  }
  state.history.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-item";
    button.innerHTML = `<span class="history-mode">최근 질의</span><span class="history-text"></span>`;
    button.querySelector(".history-text").textContent = item.request;
    button.addEventListener("click", () => {
      $("#requestInput").value = item.request;
      $("#requestInput").focus();
    });
    list.appendChild(button);
  });
}

function setBusy(isBusy) {
  $("#requestForm").classList.toggle("busy", isBusy);
  $("#requestForm").setAttribute("aria-busy", String(isBusy));
  $("#runButton").disabled = isBusy;
  $("#runButton span").textContent = isBusy ? "응답 중" : "보내기";
}

function statusChip(text, type = "") {
  const chip = document.createElement("span");
  chip.className = `status-chip ${type}`.trim();
  chip.textContent = text;
  return chip;
}

function renderStatus(response, errorText = "") {
  const strip = $("#statusStrip");
  if (!strip) {
    return;
  }
  strip.innerHTML = "";
  if (errorText) {
    strip.appendChild(statusChip(errorText, "error"));
    return;
  }
  if (!response) {
    strip.appendChild(statusChip("대기"));
    return;
  }
  strip.appendChild(statusChip(response.mode || "unknown", "mode"));
  (response.symbols || []).slice(0, 8).forEach((symbol) => {
    strip.appendChild(statusChip(symbol, "symbol"));
  });
}

function appendMessage(className, icon, meta, contentBuilder) {
  const article = document.createElement("article");
  article.className = `message ${className}`;
  article.innerHTML = `
    <div class="message-icon"><i data-lucide="${icon}"></i></div>
    <div class="message-content">
      <div class="message-meta"></div>
    </div>
  `;
  article.querySelector(".message-meta").textContent = meta;
  contentBuilder(article.querySelector(".message-content"));
  $("#conversation").appendChild(article);
  initIcons();
  article.scrollIntoView({ behavior: "smooth", block: "end" });
  return article;
}

function appendUserCommand(command) {
  appendMessage("user-message", "user", "사용자", (content) => {
    const text = document.createElement("div");
    text.className = "message-text";
    text.textContent = command.request || "오늘 미국장 체크포인트 정리해줘";
    content.appendChild(text);
  });
}

function compactResponseItems(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function cleanAgentLine(line) {
  return line
    .replace(/^Market Summary:/i, "시장 요약:")
    .replace(/^YF Quote:/i, "시세:")
    .replace(/^YF Options:/i, "옵션:")
    .replace(/^YF Fundamentals:/i, "기초지표:")
    .replace(/^YF News:/i, "뉴스:");
}

function cleanSummary(summary) {
  return summary
    .replace(/^TradingView 느낌의 technical snapshot을 준비했습니다:\s*(.+)$/i, "$1 기술 지표는 이렇게 보입니다.")
    .replace(/^종목 리뷰 관점에서\s+(.+?)\s+핵심 포인트를 정리했습니다\.$/, "$1 기준으로 보면 이렇게 정리됩니다.")
    .replace(/^브리프 관점에서\s+(.+?)\s+핵심 포인트를 정리했습니다\.$/, "$1 기준으로 보면 이렇게 정리됩니다.")
    .replace(/^(.+?)\s+핵심 포인트를 정리했습니다\.$/, "$1 핵심만 정리하면 이렇습니다.");
}

function shouldHideSegment(segment) {
  return /저장된\s+(뉴스|실적|데이터).*없음|실적 일정 없음|뉴스 없음|요약 없음/.test(segment);
}

function formatChatDetail(line) {
  const normalized = cleanAgentLine(line).replace(/^다음으로는[:：]\s*/i, "");
  const parts = normalized
    .split(/\s*\/\s*/)
    .map((part) => part.trim())
    .filter((part) => part && !shouldHideSegment(part));
  const text = (parts.length ? parts : [normalized]).join("\n  ");
  return text.replace(/^([A-Z0-9.-]+)\s+촉매:/, "$1는 촉매:");
}

function buildNaturalAnswer(response) {
  const summary = cleanSummary(String(response?.summary || "").trim());
  const lines = [
    ...compactResponseItems(response?.focus),
    ...compactResponseItems(response?.next_actions)
  ].map(cleanAgentLine);
  const seen = new Set();
  const details = lines.filter((line) => {
    if (!line || line === summary || seen.has(line)) {
      return false;
    }
    seen.add(line);
    return true;
  });
  const answer = [];
  if (summary) {
    answer.push(summary);
  }
  if (details.length) {
    answer.push("", ...details.slice(0, 5).map((line) => `• ${formatChatDetail(line)}`));
  }
  return answer.join("\n") || "답변을 만들지 못했습니다. 질의를 조금 더 구체적으로 입력해 주세요.";
}

function appendAgentResponse(answerText) {
  appendMessage("assistant-message", "sparkles", "agent", (content) => {
    const answer = document.createElement("div");
    answer.className = "agent-answer";
    answer.textContent = answerText;
    content.appendChild(answer);
  });
}

function appendThinkingMessage() {
  return appendMessage("assistant-message thinking-message", "sparkles", "agent", (content) => {
    const row = document.createElement("div");
    row.className = "typing-row";
    row.innerHTML = "<span></span><span></span><span></span>";
    content.appendChild(row);
  });
}

function removeMessage(message) {
  if (message && message.parentNode) {
    message.parentNode.removeChild(message);
  }
}

function renderResponse(response) {
  state.response = response;
  const answerText = buildNaturalAnswer(response);
  appendAgentResponse(answerText);
  state.messages.push({ role: "assistant", content: answerText });
  renderModelStatus(response);
  renderStatus(response);
}

function renderError(errorText, command) {
  if (command) {
    appendUserCommand(command);
  }
  appendMessage("error-message", "triangle-alert", "오류", (content) => {
    const text = document.createElement("div");
    text.className = "message-text";
    text.textContent = errorText;
    content.appendChild(text);
  });
  renderStatus(null, errorText);
}

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.error || "health check failed");
    }
    $("#agentStatus").textContent = "연결됨";
    renderModelStatus();
    renderWatchlist(payload.watchlist || []);
  } catch (error) {
    $("#agentStatus").textContent = "연결 실패";
    $("#topMeta").textContent = error.message || "연결 실패";
  }
}

async function runRequest(event) {
  event.preventDefault();
  saveModelSettings();
  const command = {
    request: $("#requestInput").value.trim()
  };
  if (!command.request) {
    $("#requestInput").focus();
    return;
  }
  appendUserCommand(command);
  state.messages.push({ role: "user", content: command.request });
  $("#requestInput").value = "";
  setBusy(true);
  $("#topMeta").textContent = "응답 작성 중";
  renderStatus(null);
  const thinkingMessage = appendThinkingMessage();
  try {
    const res = await fetch("/api/respond", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...command,
        history: state.messages.slice(-12),
        llm_model: state.modelSettings.model,
        llm_reasoning_effort: state.modelSettings.reasoning
      })
    });
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      throw new Error(payload.error || "request failed");
    }
    removeMessage(thinkingMessage);
    renderResponse(payload.response);
    saveHistory(command);
  } catch (error) {
    removeMessage(thinkingMessage);
    renderError(error.message || String(error));
  } finally {
    setBusy(false);
    $("#requestInput").focus();
  }
}

function setupEvents() {
  $("#requestForm").addEventListener("submit", runRequest);
  $("#refreshButton").addEventListener("click", loadHealth);
  $("#clearButton").addEventListener("click", () => {
    $("#requestInput").value = "";
    $("#requestInput").focus();
  });
  $("#requestInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("#requestForm").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupModelControls();
  renderPrompts();
  renderTemplates();
  renderHistory();
  setupEvents();
  renderStatus(null);
  await loadHealth();
  initIcons();
});
