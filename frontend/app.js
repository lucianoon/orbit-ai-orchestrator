// ===== Configuration =====
const API_BASE_URL = 'http://127.0.0.1:8000';
const WS_BASE_URL = 'ws://127.0.0.1:8000';

// ===== DOM Elements =====
const themeToggle = document.getElementById('themeToggle');
const goalInput = document.getElementById('goalInput');
const wideMode = document.getElementById('wideMode');
const executeBtn = document.getElementById('executeBtn');
const stepsSection = document.getElementById('stepsSection');
const stepsList = document.getElementById('stepsList');
const loadingSpinner = document.getElementById('loadingSpinner');
const resultsSection = document.getElementById('resultsSection');
const resultsHeader = document.getElementById('resultsHeader');
const resultsContent = document.getElementById('resultsContent');
const errorSection = document.getElementById('errorSection');
const errorContent = document.getElementById('errorContent');
const copyResultsBtn = document.getElementById('copyResultsBtn');
const exportJsonBtn = document.getElementById('exportJsonBtn');
const exportMarkdownBtn = document.getElementById('exportMarkdownBtn');
const newTaskBtn = document.getElementById('newTaskBtn');
const retryBtn = document.getElementById('retryBtn');

// ===== State =====
let currentResult = null;
let isExecuting = false;
let websocket = null;
let stepsData = [];

// ===== Theme Toggle =====
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
        themeToggle.querySelector('.icon').textContent = '☀️';
    }
}

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('light-theme');
    const isLight = document.body.classList.contains('light-theme');
    themeToggle.querySelector('.icon').textContent = isLight ? '☀️' : '🌙';
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
});

// ===== Generate Task ID =====
function generateTaskId() {
    return 'task-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

// ===== WebSocket Connection =====
function connectWebSocket(taskId) {
    return new Promise((resolve, reject) => {
        websocket = new WebSocket(`${WS_BASE_URL}/ws/${taskId}`);

        websocket.onopen = () => {
            console.log('WebSocket connected');
            resolve(websocket);
        };

        websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            reject(error);
        };

        websocket.onclose = () => {
            console.log('WebSocket closed');
        };

        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };
    });
}

// ===== Handle WebSocket Messages =====
function handleWebSocketMessage(data) {
    console.log('WS Message:', data);

    switch (data.type) {
        case 'planning_started':
            stepsList.innerHTML = `
                <div class="step-item running">
                    <span class="step-status">🧠</span>
                    <div class="step-content">
                        <div class="step-text">Planejando passos com IA...</div>
                    </div>
                </div>
            `;
            break;

        case 'steps_planned':
            stepsData = data.steps;
            renderSteps();
            break;

        case 'step_started':
            if (stepsData[data.index]) {
                stepsData[data.index].status = 'running';
                renderSteps();
            }
            break;

        case 'step_completed':
            if (stepsData[data.index]) {
                stepsData[data.index].status = 'completed';
                stepsData[data.index].output = data.output;
                stepsData[data.index].evidence = data.evidence;
                renderSteps();
            }
            break;

        case 'step_failed':
            if (stepsData[data.index]) {
                stepsData[data.index].status = 'failed';
                stepsData[data.index].error = data.error;
                renderSteps();
            }
            break;

        case 'verifying':
            stepsList.innerHTML += `
                <div class="step-item running">
                    <span class="step-status">🔍</span>
                    <div class="step-content">
                        <div class="step-text">Verificando resultados...</div>
                    </div>
                </div>
            `;
            break;

        case 'completed':
            currentResult = data;
            loadingSpinner.style.display = 'none';
            displayResults(data);
            finishExecution();
            break;

        case 'error':
            showError(data.message);
            finishExecution();
            break;
    }
}

// ===== Render Steps =====
function renderSteps() {
    stepsList.innerHTML = stepsData.map((step, index) => {
        const statusIcon = {
            'pending': '⏳',
            'running': '🔄',
            'completed': '✅',
            'failed': '❌'
        }[step.status] || '⏳';

        return `
            <div class="step-item ${step.status}">
                <span class="step-status">${statusIcon}</span>
                <div class="step-content">
                    <div class="step-text">${escapeHtml(step.text)}</div>
                    ${step.output ? `<div class="step-output">${escapeHtml(step.output)}</div>` : ''}
                    ${step.error ? `<div class="step-output" style="color: var(--error);">${escapeHtml(step.error)}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// ===== Execute Task =====
executeBtn.addEventListener('click', executeTask);
goalInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
        executeTask();
    }
});

async function executeTask() {
    const goal = goalInput.value.trim();

    if (!goal) {
        showError('Por favor, digite um objetivo para executar.');
        goalInput.focus();
        return;
    }

    if (isExecuting) return;

    isExecuting = true;
    stepsData = [];
    executeBtn.disabled = true;
    executeBtn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Conectando...</span>';

    // Reset UI
    hideAllSections();
    showStepsSection();

    const taskId = generateTaskId();

    try {
        // Try WebSocket first
        await connectWebSocket(taskId);

        executeBtn.innerHTML = '<span class="btn-icon">🔄</span><span class="btn-text">Executando...</span>';

        // Send execute command via WebSocket
        websocket.send(JSON.stringify({
            action: 'execute',
            goal: goal,
            wide: wideMode.checked
        }));

    } catch (error) {
        console.log('WebSocket failed, falling back to REST API');
        // Fallback to REST API
        await executeTaskREST(goal, wideMode.checked);
    }
}

async function executeTaskREST(goal, wide) {
    executeBtn.innerHTML = '<span class="btn-icon">🔄</span><span class="btn-text">Executando...</span>';

    stepsList.innerHTML = `
        <div class="step-item running">
            <span class="step-status">🔄</span>
            <div class="step-content">
                <div class="step-text">Processando tarefa...</div>
            </div>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE_URL}/task`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ goal, wide })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Erro HTTP: ${response.status}`);
        }

        const result = await response.json();
        currentResult = result;

        displaySteps(result.steps);

        setTimeout(() => {
            displayResults(result);
            loadingSpinner.style.display = 'none';
        }, 500);

    } catch (error) {
        console.error('Error:', error);
        showError(error.message || 'Ocorreu um erro ao executar a tarefa.');
    } finally {
        finishExecution();
    }
}

function finishExecution() {
    isExecuting = false;
    executeBtn.disabled = false;
    executeBtn.innerHTML = '<span class="btn-icon">🚀</span><span class="btn-text">Executar</span>';

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.close();
    }
}

// ===== Display Functions =====
function showStepsSection() {
    stepsSection.style.display = 'block';
    loadingSpinner.style.display = 'inline-block';
}

function hideAllSections() {
    stepsSection.style.display = 'none';
    resultsSection.style.display = 'none';
    errorSection.style.display = 'none';
}

function displaySteps(steps) {
    stepsList.innerHTML = steps.map((step, index) => `
        <div class="step-item completed">
            <span class="step-status">✅</span>
            <div class="step-content">
                <div class="step-text">${escapeHtml(step.step)}</div>
                ${step.output ? `
                    <div class="step-output">${escapeHtml(step.output)}</div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function displayResults(result) {
    resultsSection.style.display = 'block';

    // Header with verification status
    const isVerified = result.verified;
    resultsHeader.className = `results-header ${isVerified ? 'verified' : 'failed'}`;
    resultsHeader.innerHTML = `
        <div class="verification-badge ${isVerified ? 'success' : 'error'}">
            <span>${isVerified ? '✅' : '❌'}</span>
            <span>${isVerified ? 'Verificado' : 'Falha na Verificação'}</span>
        </div>
        <div class="results-summary">${escapeHtml(result.summary)}</div>
    `;

    // Generate structured markdown content
    const markdownContent = generateMarkdownReport(result);

    // Render markdown in results content
    resultsContent.innerHTML = `
        <div class="markdown-output">
            ${typeof marked !== 'undefined' ? marked.parse(markdownContent) : `<pre>${escapeHtml(markdownContent)}</pre>`}
        </div>
    `;

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showError(message) {
    hideAllSections();
    errorSection.style.display = 'block';
    errorContent.textContent = message;
    finishExecution();
}

// ===== Action Buttons =====
copyResultsBtn.addEventListener('click', () => {
    if (!currentResult) return;

    const text = formatResultsAsText(currentResult);
    navigator.clipboard.writeText(text).then(() => {
        copyResultsBtn.innerHTML = '<span class="btn-icon">✅</span> Copiado!';
        setTimeout(() => {
            copyResultsBtn.innerHTML = '<span class="btn-icon">📋</span> Copiar';
        }, 2000);
    });
});

exportJsonBtn.addEventListener('click', () => {
    if (!currentResult) return;

    const json = JSON.stringify(currentResult, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `oliver-result-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
});

exportMarkdownBtn.addEventListener('click', () => {
    if (!currentResult) return;

    const markdown = generateMarkdownReport(currentResult);
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `oliver-relatorio-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);

    exportMarkdownBtn.innerHTML = '<span class="btn-icon">✅</span> Baixado!';
    setTimeout(() => {
        exportMarkdownBtn.innerHTML = '<span class="btn-icon">📄</span> Baixar Markdown';
    }, 2000);
});

newTaskBtn.addEventListener('click', () => {
    goalInput.value = '';
    currentResult = null;
    stepsData = [];
    hideAllSections();
    goalInput.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

retryBtn.addEventListener('click', () => {
    hideAllSections();
    executeTask();
});

// ===== Utility Functions =====
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatResultsAsText(result) {
    let text = `🎯 Objetivo: ${result.goal}\n\n`;
    text += `📋 Passos:\n`;
    result.steps.forEach((step, i) => {
        text += `\n${step.step}\n`;
        text += `   ${step.output}\n`;
    });
    text += `\n✅ Status: ${result.verified ? 'Verificado' : 'Não Verificado'}\n`;
    text += `📝 Resumo: ${result.summary}`;
    return text;
}

function generateMarkdownReport(result) {
    const date = new Date().toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });

    let md = `# 📋 Relatório de Pesquisa\n\n`;
    md += `**Data:** ${date}\n\n`;
    md += `---\n\n`;
    md += `## 🎯 Objetivo\n\n`;
    md += `${result.goal}\n\n`;
    md += `---\n\n`;
    md += `## 📊 Resumo\n\n`;
    md += `${result.summary || 'Sem resumo disponível.'}\n\n`;
    md += `**Status:** ${result.verified ? '✅ Verificado' : '❌ Não Verificado'}\n\n`;
    md += `---\n\n`;
    md += `## 📑 Resultados Detalhados\n\n`;

    result.steps.forEach((step, index) => {
        md += `### ${index + 1}. ${step.step}\n\n`;
        md += `${step.output || 'Sem output.'}\n\n`;

        if (step.evidence && step.evidence.length > 0) {
            md += `**📌 Fontes:**\n\n`;
            step.evidence.forEach(ev => {
                if (ev.url) {
                    md += `- [${ev.title || ev.url}](${ev.url})\n`;
                    if (ev.snippet) {
                        md += `  > ${ev.snippet.substring(0, 150)}...\n`;
                    }
                }
            });
            md += `\n`;
        }
        md += `---\n\n`;
    });

    md += `\n---\n\n`;
    md += `*Gerado por Orbit AI Orchestrator*\n`;

    return md;
}

// ===== Initialize =====
initTheme();

// Focus on input on load
goalInput.focus();

// Add keyboard shortcut hint
goalInput.setAttribute('title', 'Pressione Ctrl+Enter para executar');

// Connection status indicator
console.log('🤖 Orbit AI Frontend initialized');
console.log(`📡 API: ${API_BASE_URL}`);
console.log(`🔌 WebSocket: ${WS_BASE_URL}`);

// ===== History =====
const historyBtn = document.getElementById('historyBtn');
const historyModal = document.getElementById('historyModal');
const closeHistoryBtn = document.getElementById('closeHistoryBtn');
const historyList = document.getElementById('historyList');

historyBtn.addEventListener('click', loadHistory);
closeHistoryBtn.addEventListener('click', closeHistoryModal);
historyModal.addEventListener('click', (e) => {
    if (e.target === historyModal) closeHistoryModal();
});

function closeHistoryModal() {
    historyModal.style.display = 'none';
}

async function loadHistory() {
    historyModal.style.display = 'flex';
    historyList.innerHTML = '<div class="history-empty">⏳ Carregando histórico...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/history?limit=20`);
        if (!response.ok) throw new Error('Failed to load history');

        const data = await response.json();

        if (!data.tasks || data.tasks.length === 0) {
            historyList.innerHTML = '<div class="history-empty">📭 Nenhuma tarefa encontrada</div>';
            return;
        }

        historyList.innerHTML = data.tasks.map(task => `
            <div class="history-item" data-id="${task.id}">
                <div class="history-info">
                    <div class="history-goal">${escapeHtml(task.goal)}</div>
                    <div class="history-meta">
                        <span>📅 ${formatDate(task.created_at)}</span>
                        <span>📋 ${task.steps_count || 0} passos</span>
                    </div>
                </div>
                <span class="history-status ${task.status}">${statusLabel(task.status)}</span>
            </div>
        `).join('');

        // Add click handlers
        historyList.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => loadTaskDetail(item.dataset.id));
        });

    } catch (error) {
        console.error('History error:', error);
        historyList.innerHTML = '<div class="history-empty">❌ Erro ao carregar histórico</div>';
    }
}

async function loadTaskDetail(taskId) {
    try {
        const response = await fetch(`${API_BASE_URL}/history/${taskId}`);
        if (!response.ok) throw new Error('Failed to load task');

        const task = await response.json();
        closeHistoryModal();

        // Display the task in the UI
        goalInput.value = task.goal;
        currentResult = {
            goal: task.goal,
            steps: task.steps.map(s => ({
                step: s.step_text,
                output: s.output || '',
                evidence: s.evidence || []
            })),
            verified: task.verified,
            summary: task.summary || ''
        };

        displaySteps(currentResult.steps);
        displayResults(currentResult);

    } catch (error) {
        console.error('Task detail error:', error);
        alert('Erro ao carregar detalhes da tarefa');
    }
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function statusLabel(status) {
    const labels = {
        'completed': '✅ Concluída',
        'failed': '❌ Falhou',
        'executing': '🔄 Executando',
        'planning': '🧠 Planejando',
        'pending': '⏳ Pendente'
    };
    return labels[status] || status;
}

