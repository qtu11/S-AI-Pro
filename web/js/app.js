/**
 * S-AI-Pro v6.0 — Dashboard App
 * Premium UI: Chat, Live Screen, Activity Feed, Thinking Panel.
 * 5-Layer Cognitive Architecture Dashboard Controller.
 * Copyright © 2025-2026 Qtus Dev (Anh Tú)
 */

const App = (() => {
  // ═══ STATE ═══
  const state = {
    connected: false,
    agentRunning: false,
    agentPaused: false,
    currentStep: 0,
    maxSteps: 0,
    currentGoal: '',
    theme: localStorage.getItem('theme') || 'dark',
    logs: [],
    chatMessages: [],
    thinkingItems: [],
    subTasks: [],
    stats: { steps: 0, actions: 0, success: 0, time: 0, switches: 0, verifyRate: 0 },
    startTime: 0,
    timerInterval: null,
  };

  // ═══ INIT ═══
  function init() {
    applyTheme(state.theme);
    setupWebSocket();
    setupKeyboard();
    setupTextareaAutoResize();
    fetchModels();
    fetchDbStatus();
    console.log('🤖 S-AI-Pro v6.0 — Dashboard initialized');
  }

  // ═══ WEBSOCKET ═══
  function setupWebSocket() {
    wsClient.on('connected', () => {
      state.connected = true;
      updateConnectionUI(true);
    });

    wsClient.on('disconnected', () => {
      state.connected = false;
      updateConnectionUI(false);
    });

    wsClient.on('health', (data) => {
      updateApiKeys(data.keys || {});
    });

    wsClient.on('system_info', (data) => {
      updateSystemInfo(data);
    });

    wsClient.on('agent_log', (data) => {
      addActivityItem(data.event, data.message, data.step);
      if (['done', 'error'].includes(data.event)) {
        addChatMessage('agent', data.message);
      }
    });

    wsClient.on('agent_status', (data) => {
      updateAgentStatus(data.status, data.step, data.max_steps, data.goal);
    });

    wsClient.on('agent_screenshot', (data) => {
      updateScreenImage(data.image);
    });

    wsClient.on('agent_action', (data) => {
      state.stats.actions++;
      if (data.result && data.result.ok) state.stats.success++;
      updateStats();
    });

    wsClient.on('agent_complete', (data) => {
      state.agentRunning = false;
      state.agentPaused = false;
      stopTimer();
      updateAgentUI(false);
      state.stats.time = data.duration || 0;
      updateStats();
      const msg = data.success
        ? `✅ Hoàn thành! ${data.steps} bước trong ${data.duration}s`
        : `⏱️ Kết thúc sau ${data.steps} bước (${data.duration}s)`;
      addChatMessage('system', msg);
      showToast(msg, data.success ? 'success' : 'warning');
    });

    wsClient.on('agent_thinking', (data) => {
      addThinkingItem('thought', data.thought || '');
      if (data.plan) addThinkingItem('plan', data.plan);
    });

    wsClient.on('subtask_update', (data) => {
      updateSubTask(data);
    });

    wsClient.on('system_metrics', (data) => {
      updateMetrics(data);
    });

    wsClient.connect();
  }

  // ═══ AGENT CONTROL ═══
  function runAgent() {
    const input = document.getElementById('chatInput');
    const goal = input.value.trim();
    if (!goal) {
      showToast('Nhập mục tiêu trước!', 'warning');
      input.focus();
      return;
    }

    if (state.agentRunning) {
      showToast('Agent đang chạy! Dừng trước khi bắt đầu mới.', 'warning');
      return;
    }

    // Reset
    state.stats = { steps: 0, actions: 0, success: 0, time: 0, switches: 0, verifyRate: 0 };
    state.currentGoal = goal;
    state.subTasks = [];
    state.thinkingItems = [];

    addChatMessage('user', goal);
    input.value = '';
    autoResizeTextarea(input);

    const welcome = document.getElementById('chatWelcome');
    if (welcome) welcome.style.display = 'none';

    // Reset subtask bar
    const subtasksBar = document.getElementById('subtasksBar');
    if (subtasksBar) subtasksBar.style.display = 'none';

    // Clear thinking
    clearThinking();

    const provider = document.getElementById('brainProvider').value;
    const brainModel = document.getElementById('brainModel').value;
    const eyeProvider = document.getElementById('eyeProvider').value;
    const maxSteps = parseInt(document.getElementById('maxSteps').value) || 15;
    const decompose = document.getElementById('enableDecompose')?.value !== 'false';
    const deepThink = document.getElementById('enableDeepThink')?.value === 'true';

    wsClient.send({
      type: 'agent_start',
      goal: goal,
      provider: provider,
      brain_model: brainModel,
      eye_provider: eyeProvider,
      max_steps: maxSteps,
      step_delay: 0.5,
      decompose: decompose,
      deep_think: deepThink,
    });

    state.agentRunning = true;
    state.agentPaused = false;
    updateAgentUI(true);
    startTimer();
    addChatMessage('system', `🚀 Agent v6.0 khởi chạy — ${provider}/${brainModel}`);
    if (decompose) addChatMessage('system', '📊 Task Decomposition: BẬT');
    if (deepThink) addChatMessage('system', '🧠 Deep Thinking: BẬT');
  }

  function stopAgent() {
    wsClient.send({ type: 'agent_stop' });
    state.agentRunning = false;
    state.agentPaused = false;
    stopTimer();
    updateAgentUI(false);
    addChatMessage('system', '⛔ Agent đã dừng');
  }

  function pauseAgent() {
    if (!state.agentRunning) return;

    if (state.agentPaused) {
      wsClient.send({ type: 'agent_resume' });
      state.agentPaused = false;
      updateAgentUI(true);
      addChatMessage('system', '▶️ Agent tiếp tục');
    } else {
      wsClient.send({ type: 'agent_pause' });
      state.agentPaused = true;
      const badge = document.getElementById('agentBadge');
      badge.className = 'agent-badge paused';
      badge.textContent = 'Paused';
      const btnPause = document.getElementById('btnPause');
      if (btnPause) btnPause.innerHTML = '<span>▶️</span>';
      addChatMessage('system', '⏸️ Agent tạm dừng');
    }
  }

  function captureScreen() {
    wsClient.send({ type: 'capture_screen' });
  }

  // ═══ UI UPDATES ═══
  function updateConnectionUI(connected) {
    const badge = document.getElementById('connectionStatus');
    const text = document.getElementById('connectionText');
    if (connected) {
      badge.className = 'connection-badge connected';
      text.textContent = 'Đã kết nối';
    } else {
      badge.className = 'connection-badge disconnected';
      text.textContent = 'Mất kết nối';
    }
  }

  function updateAgentUI(running) {
    const btnRun = document.getElementById('btnRun');
    const btnStop = document.getElementById('btnStop');
    const btnPause = document.getElementById('btnPause');
    const badge = document.getElementById('agentBadge');

    if (running) {
      btnRun.classList.add('hidden');
      btnStop.classList.remove('hidden');
      if (btnPause) {
        btnPause.classList.remove('hidden');
        btnPause.innerHTML = '<span>⏸</span>';
      }
      badge.className = 'agent-badge running';
      badge.textContent = 'Running';
    } else {
      btnRun.classList.remove('hidden');
      btnStop.classList.add('hidden');
      if (btnPause) btnPause.classList.add('hidden');
      badge.className = 'agent-badge idle';
      badge.textContent = 'Idle';
    }
  }

  function updateAgentStatus(status, step, maxSteps, goal) {
    const stateIcon = document.getElementById('agentStateIcon');
    const stateText = document.getElementById('agentStateText');
    const progress = document.getElementById('agentProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const badge = document.getElementById('agentBadge');
    const providerBadge = document.getElementById('providerBadge');

    state.currentStep = step;
    state.maxSteps = maxSteps;
    state.stats.steps = step;

    const icons = {
      planning: '📋', seeing: '👁️', thinking: '🧠',
      acting: '✋', provider_switch: '🔄',
    };
    const labels = {
      planning: 'Lập kế hoạch', seeing: 'Quan sát', thinking: 'Suy nghĩ',
      acting: 'Thực thi', provider_switch: 'Đổi Provider',
    };

    stateIcon.textContent = icons[status] || '🤖';
    stateText.textContent = labels[status] || status;

    if (status === 'provider_switch') {
      state.stats.switches++;
      providerBadge.textContent = `🔄 ${goal}`;
      showToast(goal, 'warning');
    }

    if (maxSteps > 0) {
      progress.classList.remove('hidden');
      const pct = Math.round((step / maxSteps) * 100);
      progressFill.style.width = pct + '%';
      progressText.textContent = `${step}/${maxSteps}`;
    }

    if (['thinking', 'seeing'].includes(status)) {
      badge.className = 'agent-badge thinking';
      badge.textContent = 'Thinking';
    } else if (status === 'acting') {
      badge.className = 'agent-badge running';
      badge.textContent = 'Acting';
    }

    updateStats();
  }

  function updateScreenImage(b64) {
    const img = document.getElementById('screenImage');
    const overlay = document.getElementById('screenOverlay');
    if (b64) {
      img.src = 'data:image/jpeg;base64,' + b64;
      img.classList.remove('hidden');
      overlay.classList.add('hidden');
    }
  }

  // ═══ CHAT ═══
  function addChatMessage(role, text) {
    const container = document.getElementById('chatMessages');
    const msg = document.createElement('div');
    msg.className = `chat-msg ${role}`;
    msg.textContent = text;
    container.appendChild(msg);
    const chatArea = document.getElementById('chatArea');
    chatArea.scrollTop = chatArea.scrollHeight;
    state.chatMessages.push({ role, text, time: Date.now() });
  }

  // ═══ ACTIVITY FEED ═══
  function addActivityItem(event, message, step) {
    const feed = document.getElementById('activityFeed');
    const empty = document.getElementById('activityEmpty');
    if (empty) empty.style.display = 'none';

    const icons = {
      see: '👁️', think: '🧠', act: '✋', error: '❌',
      plan: '📋', done: '✅', system: '🔧',
    };

    const item = document.createElement('div');
    item.className = 'activity-item';

    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    const shortMsg = message.length > 200 ? message.substring(0, 200) + '...' : message;

    item.innerHTML = `
      <div class="activity-icon ${event}">${icons[event] || '📌'}</div>
      <div class="activity-body">
        <div class="activity-text">${escapeHtml(shortMsg)}</div>
        <div class="activity-time">${timeStr} · Step ${step || 0}</div>
      </div>
    `;

    feed.appendChild(item);

    while (feed.children.length > 300) {
      feed.removeChild(feed.firstChild);
    }

    feed.scrollTop = feed.scrollHeight;
    state.logs.push({ event, message, step, time: Date.now() });
  }

  function clearLogs() {
    const feed = document.getElementById('activityFeed');
    feed.innerHTML = `<div class="activity-empty" id="activityEmpty"><span>💤</span><p>Đã xoá</p></div>`;
    state.logs = [];
  }

  // ═══ THINKING PANEL (NEW) ═══
  function addThinkingItem(type, text) {
    if (!text || text.trim().length === 0) return;

    const feed = document.getElementById('thinkingFeed');
    const empty = document.getElementById('thinkingEmpty');
    if (empty) empty.style.display = 'none';

    const item = document.createElement('div');
    item.className = 'thinking-item';

    const labels = {
      thought: '💭 Suy nghĩ',
      plan: '📋 Kế hoạch',
      reasoning: '🧠 Lý luận',
      check: '🔎 Kiểm tra',
    };

    const shortText = text.length > 500 ? text.substring(0, 500) + '...' : text;

    item.innerHTML = `
      <div class="thinking-label">${labels[type] || '💭 ' + type}</div>
      <div class="thinking-text">${escapeHtml(shortText)}</div>
    `;

    feed.appendChild(item);

    while (feed.children.length > 50) {
      feed.removeChild(feed.firstChild);
    }

    feed.scrollTop = feed.scrollHeight;
    state.thinkingItems.push({ type, text, time: Date.now() });
  }

  function clearThinking() {
    const feed = document.getElementById('thinkingFeed');
    if (feed) {
      feed.innerHTML = `<div class="activity-empty" id="thinkingEmpty"><span>🧠</span><p>Agent chưa suy nghĩ</p></div>`;
    }
    state.thinkingItems = [];
  }

  // ═══ SUBTASKS (NEW) ═══
  function updateSubTask(data) {
    const bar = document.getElementById('subtasksBar');
    const list = document.getElementById('subtasksList');
    const progressText = document.getElementById('subtasksProgressText');

    if (!bar || !list) return;

    bar.style.display = 'block';

    // Update or add subtask
    let existing = list.querySelector(`[data-subtask-id="${data.id}"]`);
    if (!existing) {
      existing = document.createElement('div');
      existing.className = 'subtask-item';
      existing.setAttribute('data-subtask-id', data.id);
      list.appendChild(existing);
    }

    const icons = {
      pending: '⬜', running: '🔵', done: '✅', failed: '❌', skipped: '⏭️',
    };

    existing.className = `subtask-item ${data.status}`;
    existing.innerHTML = `
      <span class="subtask-icon">${icons[data.status] || '⬜'}</span>
      <span>${data.id}. ${escapeHtml(data.desc || '')}</span>
    `;

    // Update in state
    const idx = state.subTasks.findIndex(s => s.id === data.id);
    if (idx >= 0) {
      state.subTasks[idx] = data;
    } else {
      state.subTasks.push(data);
    }

    // Update progress text
    const done = state.subTasks.filter(s => s.status === 'done').length;
    if (progressText) progressText.textContent = `${done}/${state.subTasks.length}`;
  }

  // ═══ STATS ═══
  function updateStats() {
    const s = state.stats;
    setText('statSteps', s.steps);
    setText('statActions', s.actions);
    setText('statSuccess', s.actions > 0 ? Math.round((s.success / s.actions) * 100) + '%' : '0%');
    setText('statSwitches', s.switches);
  }

  function startTimer() {
    state.startTime = Date.now();
    stopTimer();
    state.timerInterval = setInterval(() => {
      const elapsed = Math.round((Date.now() - state.startTime) / 1000);
      setText('statTime', formatDuration(elapsed));
      setText('stepTimer', formatDuration(elapsed));
    }, 1000);
  }

  function stopTimer() {
    if (state.timerInterval) {
      clearInterval(state.timerInterval);
      state.timerInterval = null;
    }
  }

  // ═══ METRICS ═══
  function updateMetrics(data) {
    if (data.cpu !== undefined) {
      setText('metricCpu', data.cpu + '%');
      setWidth('cpuBar', data.cpu + '%');
    }
    if (data.ram) {
      setText('metricRam', data.ram.used_gb + '/' + data.ram.total_gb + 'GB');
      setWidth('ramBar', data.ram.percent + '%');
    }
  }

  // ═══ PROVIDER/MODEL ═══
  function onProviderChange() {
    const provider = document.getElementById('brainProvider').value;
    fetchModels(provider);
  }

  async function fetchModels(provider) {
    provider = provider || document.getElementById('brainProvider').value;
    try {
      const resp = await fetch(`/api/models/${provider}`);
      const data = await resp.json();
      const select = document.getElementById('brainModel');
      select.innerHTML = '';
      (data.models || []).forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        select.appendChild(opt);
      });
    } catch (e) {
      console.warn('Failed to fetch models:', e);
    }
  }

  async function fetchDbStatus() {
    try {
      const resp = await fetch('/api/health');
      const data = await resp.json();
      setText('dbStatus', data.db_status || '—');
    } catch (e) {
      setText('dbStatus', 'error');
    }
  }

  // ═══ API KEYS ═══
  function updateApiKeys(keys) {
    const container = document.getElementById('apiKeysStatus');
    if (!container) return;
    const providers = [
      ['gemini', '🔵 Gemini'], ['openai', '🟢 OpenAI'], ['anthropic', '🟣 Claude'],
      ['groq', '⚡ Groq'], ['deepseek', '🔶 DeepSeek'], ['aiml', '🌐 AIML'],
    ];
    container.innerHTML = providers.map(([key, label]) => {
      const active = keys[key];
      return `<div class="stats-row">
        <span>${label}</span>
        <span style="color:${active ? 'var(--success)' : 'var(--text-tertiary)'}">${active ? '✅ OK' : '—'}</span>
      </div>`;
    }).join('');

    // Fetch Ollama models
    fetchOllamaModels();
    fetchModelPerformance();
  }

  async function fetchOllamaModels() {
    try {
      const resp = await fetch('/api/ollama/models');
      const data = await resp.json();
      const container = document.getElementById('ollamaModels');
      if (!container) return;
      if (data.models && data.models.length) {
        container.innerHTML = data.models.map(m =>
          `<div class="stats-row"><span>🦙 ${m}</span><span style="color:var(--success)">✅</span></div>`
        ).join('');
      } else {
        container.innerHTML = '<div class="stats-row"><span>Không có model</span></div>';
      }
    } catch (e) {
      // Silent
    }
  }

  async function fetchModelPerformance() {
    try {
      const resp = await fetch('/api/models/performance');
      const data = await resp.json();
      const container = document.getElementById('modelPerformance');
      if (!container) return;
      if (data.models && data.models.length) {
        container.innerHTML = data.models.map(m =>
          `<div class="stats-row">
            <span>${m.provider}/${m.model_name}</span>
            <span>${m.total_calls} calls</span>
          </div>`
        ).join('');
      } else {
        container.innerHTML = '<div class="stats-row"><span>Chưa có dữ liệu</span></div>';
      }
    } catch (e) {
      // Silent
    }
  }

  function updateSystemInfo(data) {
    const container = document.getElementById('systemInfo');
    if (!container) return;
    container.innerHTML = `
      <div class="stats-row"><span>Python</span><span>${data.python || '—'}</span></div>
      <div class="stats-row"><span>Platform</span><span>${data.platform || '—'}</span></div>
      <div class="stats-row"><span>Architecture</span><span>5-Layer Cognitive</span></div>
    `;

    const providerBadge = document.getElementById('providerBadge');
    const provider = document.getElementById('brainProvider').value;
    providerBadge.textContent = provider;
  }

  // ═══ TEMPLATES ═══
  function useTemplate(templateId) {
    const templates = {
      open_youtube: 'Mở Google Chrome, vào youtube.com, tìm kiếm ',
      open_chrome_search: 'Mở Google Chrome, vào google.com, tìm kiếm ',
      open_notepad: 'Mở Notepad, gõ nội dung: ',
      open_vscode: 'Mở Visual Studio Code, tạo file mới',
    };
    const text = templates[templateId] || '';
    const input = document.getElementById('chatInput');
    input.value = text;
    input.focus();
    input.setSelectionRange(text.length, text.length);
    autoResizeTextarea(input);
  }

  // ═══ THEME ═══
  function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(state.theme);
    localStorage.setItem('theme', state.theme);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('themeIcon');
    if (icon) icon.textContent = theme === 'dark' ? '🌙' : '☀️';
  }

  // ═══ TABS ═══
  function switchRightTab(tabName) {
    document.querySelectorAll('.pr-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.pr-content').forEach(c => c.classList.remove('active'));

    const tab = document.querySelector(`.pr-tab[data-tab="${tabName}"]`);
    const content = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));

    if (tab) tab.classList.add('active');
    if (content) content.classList.add('active');
  }

  function togglePanel(name) {
    if (name === 'settings') switchRightTab('settings');
  }

  // ═══ KEYBOARD ═══
  function setupKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); runAgent(); }
      if (e.key === 'Escape' && state.agentRunning) { e.preventDefault(); stopAgent(); }
      if (e.key === 'F5') { e.preventDefault(); captureScreen(); }
      if (e.key === 'F6') { e.preventDefault(); pauseAgent(); }
    });
  }

  function setupTextareaAutoResize() {
    const textarea = document.getElementById('chatInput');
    if (textarea) {
      textarea.addEventListener('input', () => autoResizeTextarea(textarea));
    }
  }

  function autoResizeTextarea(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  // ═══ TOAST ═══
  function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ═══ HELPERS ═══
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function setWidth(id, width) {
    const el = document.getElementById(id);
    if (el) el.style.width = width;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatDuration(seconds) {
    if (seconds < 60) return seconds + 's';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  // ═══ STARTUP ═══
  document.addEventListener('DOMContentLoaded', init);

  // ═══ PUBLIC API ═══
  return {
    runAgent,
    stopAgent,
    pauseAgent,
    captureScreen,
    clearLogs,
    clearThinking,
    onProviderChange,
    toggleTheme,
    switchRightTab,
    togglePanel,
    useTemplate,
    showToast,
  };
})();
