/* ========================================
   Customer Agent — Reasoning Console
   Application Logic
   ======================================== */

const API_BASE = '/customer-agent-api';
let scenarios = [];
let investigationHistory = [];
let notifications = [];
let tickCount = 0;
let streamReader = null;
let currentScenario = null;

document.addEventListener('DOMContentLoaded', () => {
    initGreeting();
    initSidebar();
    initNavigation();
    initNotifications();
    loadScenarios();
    checkConnection();
});

/* ----------------------------------------
   Connection Check
   ---------------------------------------- */
async function checkConnection() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
            const health = await res.json();
            document.getElementById('connectionStatus').innerHTML =
                `<span class="status-dot green"></span><span>Connected</span>`;
        }
    } catch {
        document.getElementById('connectionStatus').innerHTML =
            '<span class="status-dot red"></span><span>Disconnected</span>';
    }
}

/* ----------------------------------------
   Greeting
   ---------------------------------------- */
function initGreeting() {
    const now = new Date();
    const hour = now.getHours();
    let greeting = 'Good morning';
    if (hour >= 12 && hour < 17) greeting = 'Good afternoon';
    else if (hour >= 17) greeting = 'Good evening';
    document.getElementById('greetingText').textContent = greeting;

    const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    document.getElementById('greetingDate').textContent =
        `${days[now.getDay()]}, ${months[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()} · ${now.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'})}`;
}

/* ----------------------------------------
   Sidebar
   ---------------------------------------- */
function initSidebar() {
    document.getElementById('toggleSidebar').addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('collapsed');
    });
    document.getElementById('startQuickBtn').addEventListener('click', () => showPage('scenarios'));
    document.getElementById('navHome').addEventListener('click', () => showPage('home'));
    document.getElementById('navScenarios').addEventListener('click', () => showPage('scenarios'));
}

/* ----------------------------------------
   Navigation
   ---------------------------------------- */
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            if (page) showPage(page);
        });
    });

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterScenarios(btn.dataset.filter);
        });
    });
}

function showPage(pageName) {
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    const page = document.getElementById(`page-${pageName}`);
    if (page) page.classList.remove('hidden');

    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-page="${pageName}"]`);
    if (navItem) navItem.classList.add('active');

    const titles = { home: 'Home', scenarios: 'Simulation Scenarios', active: 'Active Investigation', history: 'History', agents: 'Agent Registry', config: 'Configuration', data: 'Data Files', knowledge: 'Knowledge Base' };
    document.getElementById('pageTitle').textContent = titles[pageName] || pageName;

    if (pageName === 'agents') loadAgentRegistry();
    if (pageName === 'config') loadConfig();
    if (pageName === 'data') loadDataFiles();
    if (pageName === 'knowledge') loadKnowledge();
    if (pageName === 'history') renderHistory();
}

/* ----------------------------------------
   Notifications
   ---------------------------------------- */
function initNotifications() {
    document.getElementById('notifBtn').addEventListener('click', () => {
        document.getElementById('notificationPanel').classList.toggle('open');
        document.getElementById('notifDot').style.display = 'none';
        renderNotifications();
    });
    document.getElementById('closeNotifPanel').addEventListener('click', () => {
        document.getElementById('notificationPanel').classList.remove('open');
    });
}

function renderNotifications() {
    const container = document.getElementById('notificationList');
    if (!notifications.length) {
        container.innerHTML = '<div class="empty-notif">No notifications yet. Run a scenario to generate notifications.</div>';
        return;
    }
    container.innerHTML = notifications.map(n => `
        <div class="notif-item unread">
            <div class="notif-icon ${escapeHtml(n.severity || 'info')}"><i class="fas ${getNotifIcon(n.severity)}"></i></div>
            <div class="notif-content">
                <p class="notif-title">${escapeHtml(n.title)}</p>
                <p class="notif-desc">${escapeHtml(n.description)}</p>
                <p class="notif-time">${timeAgo(n.timestamp)}</p>
            </div>
        </div>
    `).join('');
}

function addNotification(title, description, severity) {
    notifications.unshift({ title, description, severity: severity || 'info', timestamp: new Date().toISOString() });
    document.getElementById('notifDot').style.display = 'block';
}

function getNotifIcon(severity) {
    const icons = { critical: 'fa-exclamation-circle', high: 'fa-exclamation-triangle', info: 'fa-info-circle', success: 'fa-check-circle' };
    return icons[severity] || 'fa-info-circle';
}

/* ----------------------------------------
   Scenarios
   ---------------------------------------- */
async function loadScenarios() {
    try {
        const res = await fetch(`${API_BASE}/api/scenarios`);
        const data = await res.json();
        scenarios = data.scenarios || data || [];
        renderScenarioGrid(scenarios);
        renderFeaturedScenarios(scenarios);
        document.getElementById('scenarioCount').textContent = `${scenarios.length} scenarios available`;
    } catch {
        document.getElementById('scenarioCount').textContent = 'Server offline';
    }
}

function renderScenarioGrid(list) {
    const grid = document.getElementById('scenarioGrid');
    grid.innerHTML = list.map(s => {
        const id = s.id || s.scenario_id || '';
        const severity = s.severity || s.expected_outcome || '';
        const category = s.category || '';
        const signalCount = s.signal_count || 0;
        const tags = s.tags || [];
        return `
        <div class="scenario-card">
            <div class="sc-header">
                <span class="sc-id">${escapeHtml(id)}</span>
                <span class="sc-severity ${escapeHtml(severity)}">${escapeHtml(severity)}</span>
            </div>
            <div class="sc-name">${escapeHtml(s.name)}</div>
            <div class="sc-desc">${escapeHtml(s.description || '')}</div>
            <div class="card-metrics">
                <span class="metric ${escapeHtml(category)}">${escapeHtml(category)}</span>
                <span class="metric single">${signalCount} signals</span>
            </div>
            <div class="sc-meta">
                ${tags.slice(0,4).map(t => `<span class="sc-tag">${escapeHtml(t)}</span>`).join('')}
            </div>
            <button class="btn-run" onclick="event.stopPropagation(); runScenario('${escapeHtml(id)}')">
                <i class="fas fa-play"></i> Run Scenario
            </button>
        </div>`;
    }).join('');
}

function renderFeaturedScenarios(list) {
    const featured = list.slice(0, 3);
    const container = document.getElementById('featuredScenarios');
    container.innerHTML = featured.map(s => {
        const id = s.id || s.scenario_id || '';
        const severity = s.severity || '';
        const category = s.category || '';
        return `
        <div class="dashboard-card" onclick="runScenario('${escapeHtml(id)}')">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-status-dot" style="background: ${severity === 'critical' ? 'var(--danger)' : 'var(--warning)'}"></span>
                    <span>${escapeHtml(s.name)}</span>
                </div>
            </div>
            <div class="card-body">
                <div class="card-metrics">
                    <span class="metric ${escapeHtml(severity)}">${escapeHtml(severity)}</span>
                    <span class="metric ${escapeHtml(category)}">${escapeHtml(category)}</span>
                </div>
                <p class="card-description">${escapeHtml((s.description || '').substring(0, 120))}...</p>
            </div>
        </div>`;
    }).join('');
}

function filterScenarios(category) {
    if (category === 'all') {
        renderScenarioGrid(scenarios);
    } else {
        renderScenarioGrid(scenarios.filter(s => (s.category || '').toLowerCase() === category.toLowerCase()));
    }
}

/* ----------------------------------------
   Investigation
   ---------------------------------------- */
// Bar segments — 1:1 with the investigation lifecycle.
// Each segment lights up exactly once as the investigation progresses.
//
// Phase         Who sets it              How
// ──────────    ───────────────────────   ──────────────────────────────
// initializing  investigation_service     On investigation start
// triage        investigation_service     First phase_change event
// hypothesizing hypothesis_selector       phase_complete: "triage"
// planning      evidence_planner          phase_complete: "hypothesizing"
// collecting    output_parser middleware  Auto on evidence_collected
// reasoning     reasoner                  phase_complete: "collecting" or auto
// acting        action_planner            phase_complete: "reasoning"
// notifying     notification_agent        phase_complete: "acting"
// complete      notification_agent        investigation_resolved: true
//
const PHASES = ['initializing', 'triage', 'hypothesizing', 'planning', 'collecting', 'reasoning', 'acting', 'notifying', 'complete'];

const PHASE_MAP = {
    'initializing': 'initializing', 'init': 'initializing',
    'triage': 'triage', 'triaging': 'triage',
    'hypothesizing': 'hypothesizing', 'hypothesis': 'hypothesizing',
    'planning': 'planning', 'plan': 'planning',
    'collecting': 'collecting', 'collection': 'collecting', 'evidence_collection': 'collecting',
    'reasoning': 'reasoning', 'reason': 'reasoning',
    'acting': 'acting', 'action': 'acting',
    'notifying': 'notifying', 'notification': 'notifying', 'notify': 'notifying',
    'complete': 'complete', 'resolved': 'complete', 'resolution': 'complete',
};

const hypothesisState = {};
let highestPhaseIdx = -1;  // Track the furthest phase reached (never regress)

function initPhaseProgress() {
    const container = document.getElementById('phaseProgress');
    highestPhaseIdx = -1;
    container.innerHTML = PHASES.map(p => `<div class="phase-step" data-phase="${p}" title="${p}"></div>`).join('');
}

function updatePhaseProgress(rawPhase) {
    const currentPhase = PHASE_MAP[(rawPhase || '').toLowerCase()] || rawPhase;
    const idx = PHASES.indexOf(currentPhase);
    if (idx < 0) return;

    // Only advance — never regress the bar
    if (idx > highestPhaseIdx) {
        highestPhaseIdx = idx;
    }

    const displayIdx = highestPhaseIdx;
    const isLastPhase = displayIdx === PHASES.length - 1;
    document.querySelectorAll('.phase-step').forEach((step, i) => {
        step.classList.remove('active');
        if (isLastPhase) {
            step.classList.add('done');
        } else if (i < displayIdx) {
            step.classList.add('done');
        } else if (i === displayIdx) {
            step.classList.add('active');
            step.classList.remove('done');
        } else {
            step.classList.remove('done');
        }
    });
}

function resetInvestigationUI(scenario) {
    const header = document.getElementById('investigationHeader');
    const id = scenario.id || scenario.scenario_id || '';
    const category = scenario.category || '';
    const signalCount = scenario.signal_count || (scenario.signals || []).length || 0;
    header.innerHTML = `
        <div class="ih-title">${escapeHtml(scenario.name)}</div>
        <div class="ih-customer">${escapeHtml(id)} · ${escapeHtml(category)}</div>
        <div class="ih-meta">
            <span><i class="fas fa-signal"></i> ${signalCount} signals</span>
            <span><i class="fas fa-tags"></i> ${escapeHtml(category)}</span>
        </div>
    `;

    const expectedOutcome = scenario.expected_outcome || '';
    const expectedRootCause = scenario.expected_root_cause || '';
    document.getElementById('expectedOutcome').innerHTML = `
        <strong><i class="fas fa-bullseye"></i> Expected Outcome:</strong> ${escapeHtml(expectedOutcome)}
        ${expectedRootCause ? `<br><strong>Expected Root Cause:</strong> ${escapeHtml(expectedRootCause)}` : ''}
    `;

    document.getElementById('agentStream').innerHTML = '';
    document.getElementById('signalsList').innerHTML = '';
    document.getElementById('symptomsList').innerHTML = '';
    document.getElementById('hypothesesList').innerHTML = '';
    document.getElementById('evidenceList').innerHTML = '';
    document.getElementById('actionsList').innerHTML = '';
    document.getElementById('resolutionPanel').classList.add('hidden');
    document.getElementById('tickCounter').textContent = 'Tick: 0';
    tickCount = 0;
    highestPhaseIdx = -1;
    Object.keys(hypothesisState).forEach(k => delete hypothesisState[k]);

    // Reset graph state
    graphState.symptoms = {};
    graphState.hypotheses = {};
    graphState.evidence = {};
    graphState.hypToSymptoms = {};
    graphState.hypToEvidence = {};
    graphState.configLoaded = false;

    // Reset agent flow
    agentFlowSequence.length = 0;

    // Reset to stream view
    switchView('stream');

    initPhaseProgress();

    document.getElementById('preInvestigation').classList.add('hidden');
    document.getElementById('activeInvestigation').classList.remove('hidden');
}

async function runScenario(scenarioId) {
    const scenario = scenarios.find(s => (s.id || s.scenario_id) === scenarioId);
    if (!scenario) return;

    // Cancel existing stream
    if (streamReader) {
        try { streamReader.cancel(); } catch {}
        streamReader = null;
    }

    currentScenario = scenario;
    showPage('active');
    resetInvestigationUI(scenario);
    showToast('info', `Investigation started for ${scenario.name}...`);

    try {
        const res = await fetch(`${API_BASE}/api/investigate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scenario_id: scenarioId }),
        });

        if (!res.ok) {
            showToast('error', 'Failed to start investigation');
            return;
        }

        const reader = res.body.getReader();
        streamReader = reader;
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line in buffer

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('data: ')) {
                    const jsonStr = trimmed.substring(6);
                    if (!jsonStr || jsonStr === '[DONE]') continue;
                    try {
                        const evt = JSON.parse(jsonStr);
                        if (evt.event_type === 'done') {
                            streamReader = null;
                            return;
                        }
                        handleStreamEvent(evt);
                    } catch {}
                }
            }
        }
        streamReader = null;
    } catch (err) {
        showToast('error', 'Failed to start investigation — is the agent server running?');
    }
}

/* ----------------------------------------
   Stream Event Handler
   ---------------------------------------- */
function handleStreamEvent(evt) {
    tickCount++;
    document.getElementById('tickCounter').textContent = `Tick: ${tickCount}`;

    if (evt.phase) {
        updatePhaseProgress(evt.phase);
    }

    addStreamEvent(evt);

    // ── Track agent turn for flow view ──
    if (evt.agent_name && evt.event_type !== 'investigation_started') {
        agentFlowSequence.push({
            tick: tickCount,
            agent: evt.agent_name,
            phase: evt.phase || '',
            eventType: evt.event_type || 'agent_turn',
            summary: (evt.content || '').substring(0, 80).replace(/\n/g, ' ').trim(),
        });
    }

    const content = evt.content || '';
    const data = evt.data || {};
    const so = data.structured_output || {};
    const jsonParsed = data.json_parsed === true;

    // Log whether this event had structured JSON
    if (!jsonParsed && evt.event_type === 'agent_turn') {
        console.warn(`[Agent ${evt.agent_name || 'unknown'}] No structured JSON in output — using regex fallback`);
    }

    // ── Extract signals from investigation_started event ──
    if (evt.event_type === 'signal_received' || evt.event_type === 'investigation_started' || evt.event_type === 'phase_change') {
        const signals = data.signals || [];
        if (Array.isArray(signals)) {
            signals.forEach(s => addSignalToSidebar(s));
        }
    }

    // ── Symptoms: from structured triage output ──
    if (so.symptoms && Array.isArray(so.symptoms)) {
        so.symptoms.forEach(sym => {
            addSymptomToSidebar(
                sym.id || `SYM-${seenSymptoms.size + 1}`,
                sym.text || sym.description || ''
            );
        });
    }

    // ── Hypotheses: from structured hypothesis_selector or reasoner output ──
    if (so.hypotheses && Array.isArray(so.hypotheses)) {
        so.hypotheses.forEach(hyp => {
            const id = hyp.id || '';
            const statement = hyp.statement || '';
            const conf = typeof hyp.confidence === 'number' ? hyp.confidence : 0;
            const status = (hyp.status || 'active').toLowerCase();
            if (id && !hypothesisState[id]) {
                addHypothesisToSidebar(id, statement, conf);
                if (conf > 0 || status !== 'active') {
                    updateHypothesisConfidence(id, conf, status);
                }
            }
        });
    }
    if (so.evaluations && Array.isArray(so.evaluations)) {
        so.evaluations.forEach(evalItem => {
            const id = evalItem.hypothesis_id || '';
            const conf = typeof evalItem.confidence === 'number' ? evalItem.confidence : 0;
            const status = (evalItem.status || 'active').toLowerCase();
            const statement = evalItem.statement || '';
            if (id) {
                if (!hypothesisState[id]) {
                    addHypothesisToSidebar(id, statement, conf);
                }
                updateHypothesisConfidence(id, conf, status);
            }
        });
    }

    // ── Preliminary verdicts from evidence collectors → partial confidence updates ──
    if (so.preliminary_verdicts && Array.isArray(so.preliminary_verdicts)) {
        so.preliminary_verdicts.forEach(pv => {
            const id = pv.hypothesis_id || '';
            const verdict = (pv.verdict || '').toUpperCase();
            if (id && hypothesisState[id]) {
                // Map verdicts to confidence increments
                let conf = hypothesisState[id].confidence || 0;
                if (verdict === 'STRONGLY_SUPPORTS') conf = Math.max(conf, 0.7);
                else if (verdict === 'SUPPORTS') conf = conf + (1 - conf) * 0.3;
                else if (verdict === 'PARTIALLY_SUPPORTS') conf = conf + (1 - conf) * 0.15;
                else if (verdict === 'REFUTES') conf = conf * 0.3;
                else if (verdict === 'STRONGLY_REFUTES') conf = 0.0;
                const status = conf >= 0.85 ? 'confirmed' : conf <= 0.1 ? 'refuted' : 'active';
                updateHypothesisConfidence(id, conf, status);
            }
        });
    }

    // ── ALWAYS parse content for hypothesis IDs with confidence ──
    // Even with structured JSON, agents often mention hypothesis status in prose.
    // This catches orchestrator summaries, reasoner narratives, etc.
    _updateHypothesesFromContent(content);

    // ── Evidence: from structured evidence collector output ──
    if (so.evidence_collected && Array.isArray(so.evidence_collected)) {
        so.evidence_collected.forEach(ev => {
            addEvidenceToSidebar(ev.id || '', ev.summary || '');
        });
    }

    // ── Actions: from structured action_planner output ──
    if (so.actions && Array.isArray(so.actions)) {
        so.actions.forEach(act => {
            addActionToSidebar(
                act.action_id || act.id || '',
                act.display_name || act.action_id || '',
                act.tier || 'executed'
            );
        });
    }

    // ── Resolution: from structured notification_agent report ──
    if (so.report) {
        window._lastStructuredReport = so.report;
    }

    // ── Track relationships for graph view ──
    _trackGraphRelationships(so, content);

    // ── Capture notification_agent content for resolution ──
    const agentName = evt.agent_name || '';
    if (agentName.includes('notification') || evt.phase === 'notifying') {
        window._lastNotificationContent = content;
    }

    // ── Investigation complete — show resolution ──
    if (evt.event_type === 'investigation_complete') {
        const report = window._lastStructuredReport || {};
        const resolutionContent = window._lastNotificationContent || content;
        showResolution(data, resolutionContent, report);
    }

    // ── Notification events ──
    if (evt.event_type === 'notification_sent') {
        addNotification(data.title || 'Investigation Update', data.description || content, data.severity || 'info');
    }

    // ── Regex fallback: only if no structured JSON was parsed ──
    if (!jsonParsed) {
        _handleStreamEventRegexFallback(content, data, evt);
    }
}

/**
 * Extract hypothesis confidence updates from agent prose text.
 * Runs on EVERY event (not just fallback) because agents often mention
 * hypothesis status in their narrative even when JSON is also present.
 */
function _updateHypothesesFromContent(content) {
    if (!content) return;
    const hypMatches = content.match(/HYP-[A-Z]+-\d+/g);
    if (!hypMatches) return;

    const uniqueHyps = [...new Set(hypMatches)];
    uniqueHyps.forEach(id => {
        // Find the section of text near this hypothesis ID
        const hypSection = content.substring(content.indexOf(id));
        let conf = 0;
        const confPatterns = [
            /confidence[:\s]+(\d+\.\d+)/i,
            /confidence[:\s]+(\d+)%/i,
            /(\d+\.\d+)\s*%?\s*\(?(?:confirmed|refuted|contributing)/i,
            /score[:\s]+(\d+\.\d+)/i,
        ];
        for (const pat of confPatterns) {
            const m = hypSection.match(pat);
            if (m) {
                conf = parseFloat(m[1]);
                if (conf > 1) conf = conf / 100;
                break;
            }
        }
        const statusMatch = hypSection.match(/\b(CONFIRMED|REFUTED|CONTRIBUTING|NEEDS_MORE_EVIDENCE|ACTIVE)\b/i);
        const status = statusMatch ? statusMatch[1].toLowerCase() : (conf >= 0.85 ? 'confirmed' : conf <= 0.1 ? 'refuted' : 'active');

        if (!hypothesisState[id]) {
            const stmtMatch = content.match(new RegExp(id + '[:\\s"]+([^\\n"]{5,80})'));
            addHypothesisToSidebar(id, stmtMatch ? stmtMatch[1].trim() : id, conf);
        }
        // Only update if we found meaningful confidence or status info
        if (conf > 0 || (statusMatch && status !== 'active')) {
            updateHypothesisConfidence(id, conf, status);
        }
    });
}

/**
 * Regex fallback for events that did not have structured JSON output.
 * This handles legacy or malformed agent responses.
 */
function _handleStreamEventRegexFallback(content, data, evt) {
    // Parse content for symptom IDs (SYM-XXX-NNN)
    const symMatches = content.match(/SYM-[A-Z]+-\d+/g);
    if (symMatches) {
        symMatches.forEach(id => {
            const textMatch = content.match(new RegExp(id + '[:\\s]+([^\\n]+)'));
            addSymptomToSidebar(id, textMatch ? textMatch[1].trim().substring(0, 80) : '');
        });
    }

    // NOTE: Hypothesis parsing is handled by _updateHypothesesFromContent()
    // which runs on EVERY event, not just fallback. No duplicate needed here.

    // Parse content for evidence IDs (ER-XXX-NNN)
    const erMatches = content.match(/ER-[A-Z]+-\d+/g);
    if (erMatches) {
        erMatches.forEach(id => {
            const summaryMatch = content.match(new RegExp(id + '[:\\s]+([^\\n]+)'));
            addEvidenceToSidebar(id, summaryMatch ? summaryMatch[1].trim().substring(0, 100) : '');
        });
    }

    // Parse content for action IDs (ACT-XXX-NNN)
    const actMatches = content.match(/ACT-[A-Z]+-\d+/g);
    if (actMatches) {
        actMatches.forEach(id => {
            const nameMatch = content.match(new RegExp(id + '[:\\s]+([^\\n]+)'));
            addActionToSidebar(id, nameMatch ? nameMatch[1].trim().substring(0, 60) : id, 'executed');
        });
    }

    // Handle evidence from data field
    if (evt.event_type === 'evidence_collected' && data.evidence_id) {
        addEvidenceToSidebar(data.evidence_id || data.er_id || '', data.result_summary || data.summary || '');
    }
}

function addStreamEvent(evt) {
    const stream = document.getElementById('agentStream');
    const div = document.createElement('div');
    div.className = `stream-event ${escapeHtml(evt.event_type || 'agent_turn')}`;

    const phaseColors = {
        signal_ingestion: 'var(--phase-signal)',
        trigger_correlation: 'var(--phase-signal)',
        triage: 'var(--phase-triage)', triaging: 'var(--phase-triage)',
        hypothesizing: 'var(--phase-hypothesis)', hypothesis: 'var(--phase-hypothesis)',
        planning: 'var(--phase-planning)',
        collecting: 'var(--phase-collecting)', collection: 'var(--phase-collecting)',
        expanding: '#d63031',
        reasoning: 'var(--phase-reasoning)',
        finalizing: '#e84393',
        acting: 'var(--phase-acting)', action: 'var(--phase-acting)',
        verifying: 'var(--phase-verifying)', verification: 'var(--phase-verifying)',
        notifying: 'var(--phase-notifying)', notification: 'var(--phase-notifying)',
        resolved: 'var(--phase-resolved)', resolution: 'var(--phase-resolved)',
        complete: 'var(--phase-resolved)',
    };
    const phase = evt.phase || '';
    const phaseColor = phaseColors[phase.toLowerCase()] || 'var(--text-muted)';

    const agentName = evt.agent_name || evt.agent || evt.event_type || '';
    const content = evt.content || '';
    const body = formatStreamBody(content, evt);

    div.innerHTML = `
        <div class="se-header">
            <span>
                <span class="se-agent">${escapeHtml(agentName)}</span>
                ${phase ? `<span class="se-phase" style="background:${phaseColor}; color:white;">${escapeHtml(phase)}</span>` : ''}
            </span>
            <span class="se-tick">#${tickCount}</span>
        </div>
        <div class="se-body">${body}</div>
    `;

    stream.appendChild(div);
    stream.scrollTop = stream.scrollHeight;
}

function formatStreamBody(content, evt) {
    if (!content && evt.data) {
        return `<span style="opacity:0.7">${escapeHtml(JSON.stringify(evt.data).substring(0, 300))}</span>`;
    }

    // Strip the ```json ... ``` block from display — it's parsed into data
    let displayContent = content.replace(/```json\s*\n[\s\S]*?```/g, '').trim();
    // Also strip legacy ---SIGNALS--- block from display
    const sigIdx = displayContent.indexOf('---SIGNALS---');
    if (sigIdx >= 0) displayContent = displayContent.substring(0, sigIdx).trim();

    // Highlight IDs in content
    let safe = escapeHtml(displayContent.substring(0, 500));
    safe = safe.replace(/(SYM-[A-Z]+-\d+)/g, '<strong style="color:var(--phase-triage)">$1</strong>');
    safe = safe.replace(/(HYP-[A-Z]+-\d+)/g, '<strong style="color:var(--phase-hypothesis)">$1</strong>');
    safe = safe.replace(/(ER-[A-Z]+-\d+)/g, '<strong style="color:var(--phase-collecting)">$1</strong>');
    safe = safe.replace(/(ACT-[A-Z]+-\d+)/g, '<strong style="color:var(--phase-acting)">$1</strong>');
    if (displayContent.length > 500) safe += '...';

    // Add structured data badge
    const jsonParsed = evt.data && evt.data.json_parsed;
    const badge = jsonParsed
        ? '<span style="float:right;font-size:9px;background:#e6f4ea;color:#28a745;padding:1px 5px;border-radius:3px;font-weight:600;">JSON ✓</span>'
        : (evt.event_type === 'agent_turn' ? '<span style="float:right;font-size:9px;background:#fef3e0;color:#f0ad4e;padding:1px 5px;border-radius:3px;font-weight:600;">FALLBACK</span>' : '');

    return `${badge}<span style="white-space:pre-wrap;">${safe}</span>`;
}

/* ----------------------------------------
   Sidebar State Updates
   ---------------------------------------- */
const seenSignals = new Set();
const seenSymptoms = new Set();
const seenEvidence = new Set();
const seenActions = new Set();

/* ----------------------------------------
   Relationship Graph — Data Tracking
   ---------------------------------------- */
// Tracks all relationships between symptoms, hypotheses, and evidence
const graphState = {
    symptoms: {},       // { 'SYM-SLI-001': { id, text } }
    hypotheses: {},     // { 'HYP-SLI-003': { id, statement, confidence, status } }
    evidence: {},       // { 'ER-CAP-001': { id, summary, verdicts: { 'HYP-SLI-003': 'SUPPORTS' } } }
    hypToSymptoms: {},  // { 'HYP-SLI-003': ['SYM-SLI-001', 'SYM-SLI-002'] }
    hypToEvidence: {},  // { 'HYP-SLI-003': ['ER-CAP-001', 'ER-SLI-001'] }
    configLoaded: false,
};

// Agent execution sequence — tracks every agent turn for the flow view
const agentFlowSequence = [];

function toggleSection(h4) {
    const section = h4.closest('.sidebar-section');
    section.classList.toggle('collapsed');
}

function _updateSectionCount(countId, count) {
    const el = document.getElementById(countId);
    if (el) el.textContent = count;
}

function addSignalToSidebar(data) {
    const key = data.signal_type || data.type || JSON.stringify(data);
    if (seenSignals.has(key)) return;
    seenSignals.add(key);
    const list = document.getElementById('signalsList');
    const div = document.createElement('div');
    div.className = 'state-item';
    div.innerHTML = `<span class="si-id">${escapeHtml(data.signal_type || data.type || '')}</span> ${escapeHtml((data.description || '').substring(0, 80))}`;
    list.appendChild(div);
    _updateSectionCount('signalsCount', seenSignals.size);
}

function addSymptomToSidebar(id, text) {
    if (seenSymptoms.has(id)) return;
    seenSymptoms.add(id);
    const list = document.getElementById('symptomsList');
    const div = document.createElement('div');
    div.className = 'state-item';
    div.innerHTML = `<span class="si-id">${escapeHtml(id)}</span> ${escapeHtml(text)}`;
    list.appendChild(div);
    _updateSectionCount('symptomsCount', seenSymptoms.size);
}

function addHypothesisToSidebar(id, statement, confidence) {
    if (hypothesisState[id]) return;
    hypothesisState[id] = { confidence: confidence || 0, status: 'active' };
    const list = document.getElementById('hypothesesList');
    const div = document.createElement('div');
    div.className = 'state-item';
    div.id = `hyp-${id}`;
    const pct = ((confidence || 0) * 100).toFixed(0);
    div.innerHTML = `
        <span class="si-id">${escapeHtml(id)}</span>
        <span class="si-conf active">${pct}%</span>
        <br>${escapeHtml(statement)}
        <div class="conf-bar"><div class="conf-bar-fill zero" style="width:${pct}%" id="conf-${id}"></div></div>
    `;
    list.appendChild(div);
    _updateSectionCount('hypothesesCount', Object.keys(hypothesisState).length);
}

function updateHypothesisConfidence(id, confidence, status) {
    if (!hypothesisState[id]) return;
    hypothesisState[id].confidence = confidence;
    hypothesisState[id].status = status;
    const el = document.getElementById(`hyp-${id}`);
    if (!el) return;
    const pct = (confidence * 100).toFixed(0);
    const statusClass = status === 'confirmed' ? 'confirmed' : status === 'refuted' ? 'refuted' : status === 'contributing' ? 'contributing' : 'active';
    const barClass = confidence >= 0.85 ? 'high' : confidence >= 0.3 ? 'mid' : confidence > 0 ? 'low' : 'zero';

    const confEl = el.querySelector('.si-conf');
    if (confEl) {
        confEl.className = `si-conf ${statusClass}`;
        confEl.textContent = `${pct}% ${status}`;
    }

    const bar = document.getElementById(`conf-${id}`);
    if (bar) {
        bar.className = `conf-bar-fill ${barClass}`;
        bar.style.width = `${pct}%`;
    }
}

function addEvidenceToSidebar(id, summary) {
    if (seenEvidence.has(id)) return;
    seenEvidence.add(id);
    const list = document.getElementById('evidenceList');
    const div = document.createElement('div');
    div.className = 'state-item';
    div.innerHTML = `<span class="si-id">${escapeHtml(id)}</span><br>${escapeHtml((summary || '').substring(0, 100))}`;
    list.appendChild(div);
    _updateSectionCount('evidenceCount', seenEvidence.size);
}

function addActionToSidebar(id, name, status) {
    if (seenActions.has(id)) return;
    seenActions.add(id);
    const list = document.getElementById('actionsList');
    const div = document.createElement('div');
    div.className = 'state-item';
    div.innerHTML = `⚡ <span class="si-id">${escapeHtml(id)}</span> ${escapeHtml(name)} — <strong>${escapeHtml(status)}</strong>`;
    list.appendChild(div);
    _updateSectionCount('actionsCount', seenActions.size);
}

/* ----------------------------------------
   Relationship Graph — Data Capture
   ---------------------------------------- */
function _trackGraphRelationships(so, content) {
    // Track symptoms
    if (so.symptoms && Array.isArray(so.symptoms)) {
        so.symptoms.forEach(s => {
            const id = s.id || '';
            if (id) graphState.symptoms[id] = { id, text: s.text || s.description || '' };
        });
    }
    // Track hypotheses and their symptom/evidence links
    if (so.hypotheses && Array.isArray(so.hypotheses)) {
        so.hypotheses.forEach(h => {
            const id = h.id || '';
            if (!id) return;
            graphState.hypotheses[id] = { id, statement: h.statement || '', confidence: h.confidence || 0, status: (h.status || 'active').toLowerCase() };
            if (h.evidence_needed) graphState.hypToEvidence[id] = [...(graphState.hypToEvidence[id] || []), ...h.evidence_needed].filter((v, i, a) => a.indexOf(v) === i);
            if (h.applicable_symptoms) graphState.hypToSymptoms[id] = [...(graphState.hypToSymptoms[id] || []), ...h.applicable_symptoms].filter((v, i, a) => a.indexOf(v) === i);
        });
    }
    // Track evidence
    if (so.evidence_collected && Array.isArray(so.evidence_collected)) {
        so.evidence_collected.forEach(e => {
            const id = (typeof e === 'string') ? e : (e.id || '');
            if (id) graphState.evidence[id] = { id, summary: (typeof e === 'object' ? e.summary : '') || '', verdicts: graphState.evidence[id]?.verdicts || {} };
        });
    }
    // Track preliminary verdicts → evidence-hypothesis links
    if (so.preliminary_verdicts && Array.isArray(so.preliminary_verdicts)) {
        so.preliminary_verdicts.forEach(pv => {
            const hid = pv.hypothesis_id || '';
            const verdict = (pv.verdict || '').toLowerCase();
            // Find which evidence this came from (use the evidence IDs from the same output)
            const evIds = Object.keys(graphState.evidence);
            if (hid && evIds.length) {
                const latestEv = evIds[evIds.length - 1];
                if (graphState.evidence[latestEv]) graphState.evidence[latestEv].verdicts[hid] = verdict;
                if (!graphState.hypToEvidence[hid]) graphState.hypToEvidence[hid] = [];
                if (!graphState.hypToEvidence[hid].includes(latestEv)) graphState.hypToEvidence[hid].push(latestEv);
            }
        });
    }
    // Track evaluations → update hypothesis + evidence verdicts
    if (so.evaluations && Array.isArray(so.evaluations)) {
        so.evaluations.forEach(ev => {
            const hid = ev.hypothesis_id || '';
            if (hid && graphState.hypotheses[hid]) {
                graphState.hypotheses[hid].confidence = ev.confidence || graphState.hypotheses[hid].confidence;
                graphState.hypotheses[hid].status = (ev.status || graphState.hypotheses[hid].status).toLowerCase();
            }
            if (ev.evidence && Array.isArray(ev.evidence)) {
                ev.evidence.forEach(eev => {
                    const eid = eev.evidence_id || '';
                    const verdict = (eev.verdict || '').toLowerCase();
                    if (eid && graphState.evidence[eid]) graphState.evidence[eid].verdicts[hid] = verdict;
                    if (eid && hid) {
                        if (!graphState.hypToEvidence[hid]) graphState.hypToEvidence[hid] = [];
                        if (!graphState.hypToEvidence[hid].includes(eid)) graphState.hypToEvidence[hid].push(eid);
                    }
                });
            }
        });
    }
    // Parse content for symptom→hypothesis associations
    const hypIds = Object.keys(graphState.hypotheses);
    const symIds = Object.keys(graphState.symptoms);
    if (hypIds.length && symIds.length && content) {
        hypIds.forEach(hid => {
            symIds.forEach(sid => {
                if (content.includes(hid) && content.includes(sid)) {
                    if (!graphState.hypToSymptoms[hid]) graphState.hypToSymptoms[hid] = [];
                    if (!graphState.hypToSymptoms[hid].includes(sid)) graphState.hypToSymptoms[hid].push(sid);
                }
            });
        });
    }
}

/* ----------------------------------------
   Relationship Graph — View Toggle
   ---------------------------------------- */
function switchView(view) {
    const panels = {
        stream: document.getElementById('streamViewPanel'),
        graph: document.getElementById('graphViewPanel'),
        flow: document.getElementById('flowViewPanel'),
    };
    const buttons = {
        stream: document.getElementById('btnStreamView'),
        graph: document.getElementById('btnGraphView'),
        flow: document.getElementById('btnFlowView'),
    };

    Object.values(panels).forEach(p => { if (p) p.classList.add('hidden'); });
    Object.values(buttons).forEach(b => { if (b) b.classList.remove('active'); });

    if (panels[view]) panels[view].classList.remove('hidden');
    if (buttons[view]) buttons[view].classList.add('active');

    if (view === 'graph') renderRelationshipGraph();
    if (view === 'flow') renderAgentFlow();
}

/* ----------------------------------------
   Relationship Graph — Rendering
   ---------------------------------------- */
async function renderRelationshipGraph() {
    const container = document.getElementById('graphContainer');

    // Load hypothesis config for evidence links only (not symptoms —
    // symptoms come solely from what triage actually extracted).
    if (!graphState.configLoaded) {
        try {
            const res = await fetch(`${API_BASE}/api/config/hypotheses`);
            const data = await res.json();
            const investigationSymIds = Object.keys(graphState.symptoms);
            (data.items || []).forEach(h => {
                if (!h.id || !graphState.hypotheses[h.id]) return; // Skip hypotheses not in this investigation
                // Only add symptoms that were actually extracted in this investigation
                if (h.applicable_symptoms && h.applicable_symptoms.length) {
                    const relevant = h.applicable_symptoms.filter(s => investigationSymIds.includes(s));
                    if (relevant.length)
                        graphState.hypToSymptoms[h.id] = [...(graphState.hypToSymptoms[h.id] || []), ...relevant].filter((v, i, a) => a.indexOf(v) === i);
                }
                // Evidence links from config are fine — they show what's needed
                if (h.evidence_needed && h.evidence_needed.length)
                    graphState.hypToEvidence[h.id] = [...(graphState.hypToEvidence[h.id] || []), ...h.evidence_needed].filter((v, i, a) => a.indexOf(v) === i);
            });
            graphState.configLoaded = true;
        } catch {}
    }

    const hyps = Object.values(graphState.hypotheses);
    if (!hyps.length) {
        container.innerHTML = '<div class="graph-empty"><i class="fas fa-project-diagram"></i><p>No hypotheses yet — run a scenario first</p></div>';
        return;
    }

    // Collect relevant symptoms and evidence for active hypotheses
    const relevantSyms = new Set();
    const relevantEvs = new Set();
    hyps.forEach(h => {
        (graphState.hypToSymptoms[h.id] || []).forEach(s => relevantSyms.add(s));
        (graphState.hypToEvidence[h.id] || []).forEach(e => relevantEvs.add(e));
    });

    const symList = [...relevantSyms];
    const evList = [...relevantEvs];

    // Build HTML
    const maxRows = Math.max(symList.length, hyps.length, evList.length, 1);

    let html = '<div class="pipeline-layout">';

    // Column 1: Symptoms
    html += '<div class="pipeline-column">';
    html += '<div class="pipeline-column-header col-symptom"><i class="fas fa-stethoscope"></i> Symptoms</div>';
    symList.forEach(sid => {
        const s = graphState.symptoms[sid] || {};
        html += `<div class="pipeline-node node-symptom" data-node-id="${escapeHtml(sid)}" data-node-type="symptom" onclick="graphNodeClick(this)">
            <div class="pn-id">${escapeHtml(sid)}</div>
            <div class="pn-text">${escapeHtml((s.text || sid).substring(0, 60))}</div>
        </div>`;
    });
    if (!symList.length) html += '<div style="font-size:11px;color:var(--text-muted);padding:8px;">No symptoms linked</div>';
    html += '</div>';

    // Column 2: Hypotheses
    html += '<div class="pipeline-column">';
    html += '<div class="pipeline-column-header col-hypothesis"><i class="fas fa-lightbulb"></i> Hypotheses</div>';
    hyps.forEach(h => {
        const pct = ((h.confidence || 0) * 100).toFixed(0);
        const confClass = h.confidence >= 0.85 ? 'high' : h.confidence >= 0.3 ? 'mid' : 'low';
        const badgeClass = h.status === 'confirmed' ? 'confirmed' : h.status === 'refuted' ? 'refuted' : h.status === 'contributing' ? 'contributing' : 'active';
        html += `<div class="pipeline-node node-hypothesis" data-node-id="${escapeHtml(h.id)}" data-node-type="hypothesis" onclick="graphNodeClick(this)">
            <span class="pn-badge ${badgeClass}">${escapeHtml(h.status || 'active')}</span>
            <div class="pn-id">${escapeHtml(h.id)}</div>
            <div class="pn-text">${escapeHtml((h.statement || h.id).substring(0, 60))}</div>
            <div class="pn-conf ${confClass}">${pct}% confidence</div>
        </div>`;
    });
    html += '</div>';

    // Column 3: Evidence
    html += '<div class="pipeline-column">';
    html += '<div class="pipeline-column-header col-evidence"><i class="fas fa-search"></i> Evidence</div>';
    evList.forEach(eid => {
        const e = graphState.evidence[eid] || {};
        // Find the strongest verdict for this evidence
        const verdicts = e.verdicts || {};
        const verdictVals = Object.values(verdicts);
        const mainVerdict = verdictVals.length ? verdictVals[0] : 'pending';
        html += `<div class="pipeline-node node-evidence" data-node-id="${escapeHtml(eid)}" data-node-type="evidence" onclick="graphNodeClick(this)">
            <div class="pn-id">${escapeHtml(eid)}</div>
            <div class="pn-text">${escapeHtml((e.summary || eid).substring(0, 60))}</div>
            ${mainVerdict ? `<span class="pn-verdict ${escapeHtml(mainVerdict)}">${escapeHtml(mainVerdict.replace('_', ' '))}</span>` : ''}
        </div>`;
    });
    if (!evList.length) html += '<div style="font-size:11px;color:var(--text-muted);padding:8px;">No evidence collected yet</div>';
    html += '</div>';

    // SVG overlay for connection lines
    html += '<svg class="graph-svg-overlay" id="graphSvg"></svg>';
    html += '</div>';

    container.innerHTML = html;

    // Draw connection lines after DOM renders
    requestAnimationFrame(() => drawGraphConnections(null));
}

/* ----------------------------------------
   Relationship Graph — Connection Lines
   ---------------------------------------- */
function drawGraphConnections(selectedHypId) {
    const svg = document.getElementById('graphSvg');
    if (!svg) return;
    const container = svg.parentElement;
    const rect = container.getBoundingClientRect();
    svg.setAttribute('width', rect.width);
    svg.setAttribute('height', rect.height);

    let paths = '';

    const hyps = Object.values(graphState.hypotheses);
    hyps.forEach(h => {
        const hypEl = container.querySelector(`[data-node-id="${h.id}"][data-node-type="hypothesis"]`);
        if (!hypEl) return;
        const hypRect = _nodeCenter(hypEl, rect, 'left');
        const hypRectR = _nodeCenter(hypEl, rect, 'right');

        // Symptom → Hypothesis lines
        (graphState.hypToSymptoms[h.id] || []).forEach(sid => {
            const symEl = container.querySelector(`[data-node-id="${sid}"][data-node-type="symptom"]`);
            if (!symEl) return;
            const symRect = _nodeCenter(symEl, rect, 'right');
            const dimmed = selectedHypId && selectedHypId !== h.id;
            paths += _bezierPath(symRect, hypRect, 'conn-symptom' + (dimmed ? ' dimmed' : ' highlighted'));
        });

        // Hypothesis → Evidence lines
        (graphState.hypToEvidence[h.id] || []).forEach(eid => {
            const evEl = container.querySelector(`[data-node-id="${eid}"][data-node-type="evidence"]`);
            if (!evEl) return;
            const evRect = _nodeCenter(evEl, rect, 'left');
            const e = graphState.evidence[eid] || {};
            const verdict = (e.verdicts || {})[h.id] || 'pending';
            const dimmed = selectedHypId && selectedHypId !== h.id;
            paths += _bezierPath(hypRectR, evRect, 'conn-' + verdict + (dimmed ? ' dimmed' : ' highlighted'));
        });
    });

    svg.innerHTML = paths;
}

function _nodeCenter(el, containerRect, side) {
    const r = el.getBoundingClientRect();
    const x = side === 'right' ? r.right - containerRect.left : r.left - containerRect.left;
    const y = r.top + r.height / 2 - containerRect.top;
    return { x, y };
}

function _bezierPath(from, to, className) {
    const midX = (from.x + to.x) / 2;
    return `<path class="${className}" d="M${from.x},${from.y} C${midX},${from.y} ${midX},${to.y} ${to.x},${to.y}" />`;
}

/* ----------------------------------------
   Relationship Graph — Node Click
   ---------------------------------------- */
function graphNodeClick(el) {
    const nodeId = el.dataset.nodeId;
    const nodeType = el.dataset.nodeType;
    const allNodes = document.querySelectorAll('.pipeline-node');
    const wasSelected = el.classList.contains('highlighted');

    // Clear all highlights
    allNodes.forEach(n => { n.classList.remove('highlighted', 'dimmed'); });

    if (wasSelected) {
        // Deselect — show all connections
        drawGraphConnections(null);
        return;
    }

    // Find the related hypothesis ID(s)
    let relatedHypIds = [];
    if (nodeType === 'hypothesis') {
        relatedHypIds = [nodeId];
    } else if (nodeType === 'symptom') {
        relatedHypIds = Object.keys(graphState.hypToSymptoms).filter(hid => (graphState.hypToSymptoms[hid] || []).includes(nodeId));
    } else if (nodeType === 'evidence') {
        relatedHypIds = Object.keys(graphState.hypToEvidence).filter(hid => (graphState.hypToEvidence[hid] || []).includes(nodeId));
    }

    // Collect all related node IDs
    const relatedNodes = new Set(relatedHypIds);
    relatedHypIds.forEach(hid => {
        (graphState.hypToSymptoms[hid] || []).forEach(s => relatedNodes.add(s));
        (graphState.hypToEvidence[hid] || []).forEach(e => relatedNodes.add(e));
    });

    // Apply highlight/dim
    allNodes.forEach(n => {
        if (relatedNodes.has(n.dataset.nodeId)) {
            n.classList.add('highlighted');
        } else {
            n.classList.add('dimmed');
        }
    });

    // Redraw connections with focus on the selected hypothesis
    const focusHyp = nodeType === 'hypothesis' ? nodeId : (relatedHypIds[0] || null);
    drawGraphConnections(focusHyp);
}

/* ----------------------------------------
   Agent Flow — Rendering
   ---------------------------------------- */
const FLOW_AGENT_ICONS = {
    orchestrator: 'fa-chess-king', triage: 'fa-filter', hypothesis_selector: 'fa-lightbulb',
    evidence_planner: 'fa-clipboard-list', telemetry_agent: 'fa-chart-line',
    outage_agent: 'fa-exclamation-triangle', support_agent: 'fa-headset',
    advisor_agent: 'fa-shield-alt', resource_agent: 'fa-server',
    reasoner: 'fa-brain', action_planner: 'fa-tasks', notification_agent: 'fa-bell',
};

const PHASE_COLORS = {
    triage: 'var(--phase-triage)', hypothesizing: 'var(--phase-hypothesis)',
    planning: 'var(--phase-planning)', collecting: 'var(--phase-collecting)',
    reasoning: 'var(--phase-reasoning)', acting: 'var(--phase-acting)',
    notifying: 'var(--phase-notifying)', complete: 'var(--success)',
    initializing: 'var(--info)',
};

function renderAgentFlow() {
    const container = document.getElementById('flowContainer');
    if (!agentFlowSequence.length) {
        container.innerHTML = '<div class="graph-empty"><i class="fas fa-route"></i><p>No agent activity yet — run a scenario first</p></div>';
        return;
    }

    // Group turns by phase
    const phaseGroups = [];
    let currentPhase = '';
    agentFlowSequence.forEach(turn => {
        const phase = turn.phase || 'unknown';
        if (phase !== currentPhase) {
            phaseGroups.push({ phase, turns: [] });
            currentPhase = phase;
        }
        phaseGroups[phaseGroups.length - 1].turns.push(turn);
    });

    // Count agents
    const agentCounts = {};
    agentFlowSequence.forEach(t => { agentCounts[t.agent] = (agentCounts[t.agent] || 0) + 1; });
    const uniqueAgents = Object.keys(agentCounts).length;

    // Build the flow
    let html = '<div class="flow-lane"><div class="flow-lane-track">';

    phaseGroups.forEach((group, gi) => {
        // Phase separator
        if (gi > 0) {
            html += `<div class="flow-phase-sep" data-phase="${escapeHtml(group.phase)}"></div>`;
        }

        group.turns.forEach((turn, ti) => {
            // Arrow connector between nodes (but not before first)
            if (gi > 0 || ti > 0) {
                html += `<div class="flow-arrow"><svg viewBox="0 0 28 20"><path d="M0,10 L20,10"/><polygon points="18,6 26,10 18,14"/></svg></div>`;
            }

            const icon = FLOW_AGENT_ICONS[turn.agent] || 'fa-robot';
            const phaseClass = 'phase-' + (turn.phase || 'initializing');
            const phaseBadge = 'p-' + (turn.phase || 'initializing');
            const displayName = turn.agent.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const shortName = displayName.length > 16 ? displayName.substring(0, 14) + '…' : displayName;

            html += `<div class="flow-node">
                <div class="flow-node-box ${phaseClass}" title="${escapeHtml(displayName)} — Tick #${turn.tick}\n${escapeHtml(turn.summary)}">
                    <span class="fn-tick">#${turn.tick}</span>
                    <div style="font-size:16px;margin-bottom:3px;color:${PHASE_COLORS[turn.phase] || 'var(--text-muted)'}"><i class="fas ${icon}"></i></div>
                    <div class="fn-agent">${escapeHtml(shortName)}</div>
                    <span class="fn-phase ${phaseBadge}">${escapeHtml(turn.phase || '?')}</span>
                    ${turn.summary ? `<div class="fn-summary">${escapeHtml(turn.summary.substring(0, 40))}</div>` : ''}
                </div>
            </div>`;
        });
    });

    html += '</div></div>';

    // Stats bar
    html += '<div class="flow-stats">';
    html += `<div class="flow-stat"><span class="flow-stat-value">${agentFlowSequence.length}</span> total turns</div>`;
    html += `<div class="flow-stat"><span class="flow-stat-value">${uniqueAgents}</span> agents used</div>`;
    html += `<div class="flow-stat"><span class="flow-stat-value">${phaseGroups.length}</span> phase transitions</div>`;

    // Per-agent counts as colored dots
    const sortedAgents = Object.entries(agentCounts).sort((a, b) => b[1] - a[1]);
    html += '<div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;">';
    sortedAgents.forEach(([agent, count]) => {
        const icon = FLOW_AGENT_ICONS[agent] || 'fa-robot';
        const name = agent.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        html += `<div class="flow-stat" title="${name}"><i class="fas ${icon}" style="font-size:10px;"></i> <span class="flow-stat-value">${count}</span></div>`;
    });
    html += '</div></div>';

    container.innerHTML = html;
}

/* ----------------------------------------
   Resolution
   ---------------------------------------- */
function showResolution(data, content, structuredReport) {
    const panel = document.getElementById('resolutionPanel');
    panel.classList.remove('hidden');

    const report = structuredReport || {};

    // ── Use structured report data first, fall back to content parsing ──
    let rootCause = report.root_cause || data.root_cause || '';
    let summary = '';
    let actions = report.recommended_actions || data.actions_taken || data.actions || [];
    let factors = report.contributing_factors || data.contributing_factors || [];
    let confidence = report.confidence || '';
    let timeline = report.timeline || [];

    // If structured report gave us data, build summary from it
    if (report.root_cause) {
        summary = `Customer: ${report.customer || 'N/A'}\n` +
                  `Investigation ID: ${report.investigation_id || data.investigation_id || 'N/A'}\n` +
                  `Status: ${report.status || 'COMPLETE'}\n` +
                  `Timestamp: ${report.timestamp || ''}\n\n` +
                  `Root Cause: ${report.root_cause}`;
    }

    // ── Fallback: regex parse from content (only if no structured data) ──
    if (!rootCause && content) {
        const rcMatch = content.match(/ROOT\s*CAUSE[:\s]+([^\n]+)/i);
        if (rcMatch) rootCause = rcMatch[1].trim();
    }
    if (!summary && content) {
        summary = content;
        const sumMatch = content.match(/(?:RESOLUTION|SUMMARY)[:\s]+([^\n]+(?:\n(?!CONTRIBUTING|RECOMMENDED|ACTIONS|TIMELINE|===)[^\n]*)*)/i);
        if (sumMatch) summary = sumMatch[1].trim();
    }
    if (!factors.length && content) {
        const cfMatch = content.match(/CONTRIBUTING\s*FACTORS[:\s]*\n((?:[-•]\s*[^\n]+\n?)+)/i);
        if (cfMatch) {
            cfMatch[1].split('\n').forEach(line => {
                const cleaned = line.replace(/^[-•]\s*/, '').trim();
                if (cleaned) factors.push(cleaned);
            });
        }
    }
    if (!confidence && content) {
        const confMatch = content.match(/CONFIDENCE[:\s]+([^\n]+)/i);
        if (confMatch) confidence = confMatch[1].trim();
    }

    panel.innerHTML = `
        <h3><i class="fas fa-check-circle"></i> Investigation Resolved</h3>
        <div class="rp-section">
            <div class="rp-label">Root Cause</div>
            <div class="rp-value">${escapeHtml(rootCause || 'See resolution summary below')}</div>
        </div>
        ${confidence ? `
        <div class="rp-section">
            <div class="rp-label">Confidence</div>
            <div class="rp-value">${escapeHtml(confidence)}</div>
        </div>` : ''}
        ${factors.length ? `
        <div class="rp-section">
            <div class="rp-label">Contributing Factors</div>
            <ul class="rp-factors">
                ${factors.map(f => `<li>${escapeHtml(typeof f === 'string' ? f : f.description || JSON.stringify(f))}</li>`).join('')}
            </ul>
        </div>` : ''}
        <div class="rp-section">
            <div class="rp-label">Resolution Summary</div>
            <div class="rp-value" style="white-space:pre-wrap;max-height:300px;overflow-y:auto;">${escapeHtml(typeof summary === 'string' ? summary.substring(0, 2000) : JSON.stringify(summary).substring(0, 2000))}</div>
        </div>
        ${actions.length ? `
        <div class="rp-section">
            <div class="rp-label">Actions Taken</div>
            <div class="rp-value">
                ${actions.map(a => `<span class="metric single" style="margin: 2px;">${escapeHtml(typeof a === 'string' ? a : a.display_name || a.action || a.name || a.id || '')} ${a.tier ? '(' + escapeHtml(a.tier) + ')' : ''} ✓</span>`).join('')}
            </div>
        </div>` : ''}
        ${timeline.length ? `
        <div class="rp-section">
            <div class="rp-label">Timeline</div>
            <div class="rp-value" style="font-size:12px;">
                ${timeline.map(t => `<div>${escapeHtml(t.timestamp || '')} — ${escapeHtml(t.event || '')}</div>`).join('')}
            </div>
        </div>` : ''}
        <div class="rp-section" style="opacity: 0.6;">
            <div class="rp-value">Total agent turns: ${tickCount}</div>
        </div>
    `;

    showToast('success', 'Investigation resolved successfully!');

    // Mark all phases as done
    document.querySelectorAll('.phase-step').forEach(s => {
        s.classList.remove('active');
        s.classList.add('done');
    });

    // Scroll the resolution panel into view
    setTimeout(() => {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);

    // Save to history
    investigationHistory.unshift({
        scenario_id: currentScenario ? (currentScenario.id || currentScenario.scenario_id) : '',
        scenario_name: currentScenario ? currentScenario.name : '',
        root_cause: rootCause,
        ticks: tickCount,
        timestamp: new Date().toISOString(),
        status: 'completed',
    });

    // Reset dedup sets for next investigation
    seenSignals.clear();
    seenSymptoms.clear();
    seenEvidence.clear();
    seenActions.clear();
}

/* ----------------------------------------
   History
   ---------------------------------------- */
function renderHistory() {
    const emptyEl = document.getElementById('historyEmpty');
    const listEl = document.getElementById('historyList');

    if (!investigationHistory.length) {
        emptyEl.classList.remove('hidden');
        listEl.innerHTML = '';
        return;
    }
    emptyEl.classList.add('hidden');

    listEl.innerHTML = investigationHistory.map(inv => {
        const isCompleted = inv.status === 'completed';
        const statusIcon = isCompleted ? 'fa-check' : 'fa-spinner fa-spin';
        const statusCls = isCompleted ? 'completed' : 'running';
        const createdStr = inv.timestamp ? new Date(inv.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';

        return `<div class="history-card">
            <div class="hc-status-icon ${statusCls}"><i class="fas ${statusIcon}"></i></div>
            <div class="hc-main">
                <div class="hc-title">${escapeHtml(inv.scenario_name)}</div>
                <div class="hc-subtitle">
                    <span>${escapeHtml(inv.scenario_id)}</span>
                </div>
                ${inv.root_cause ? `<div class="hc-cause">${escapeHtml(inv.root_cause)}</div>` : ''}
            </div>
            <div class="hc-meta">
                <span><i class="fas fa-play" style="width:14px;"></i> ${createdStr}</span>
                <span><i class="fas fa-hashtag" style="width:14px;"></i> ${inv.ticks} ticks</span>
            </div>
            <div class="hc-actions">
                <button class="hc-btn primary" onclick="runScenario('${escapeHtml(inv.scenario_id)}')">
                    <i class="fas fa-redo"></i> Re-run
                </button>
            </div>
        </div>`;
    }).join('');
}

/* ----------------------------------------
   Agent Registry
   ---------------------------------------- */
async function loadAgentRegistry() {
    try {
        const res = await fetch(`${API_BASE}/api/agents`);
        const data = await res.json();
        const agents = data.agents || data || [];
        const grid = document.getElementById('agentRegistryGrid');
        document.getElementById('agentCount').textContent = `${agents.length} agents configured`;
        grid.innerHTML = agents.map(a => `
            <div class="agent-card">
                <div class="ac-name">${escapeHtml(a.display_name || a.name)}</div>
                <div class="ac-role">${escapeHtml(a.role || '')}</div>
                <div class="ac-desc">${escapeHtml(a.description || '')}</div>
                <span class="ac-model">${escapeHtml(a.model || '')}</span>
                ${(a.technology_tags || []).length ? `<div class="ac-tags">${a.technology_tags.map(t => `<span class="ac-tag">${escapeHtml(t)}</span>`).join('')}</div>` : ''}
                ${(a.tool_names || []).length ? `<div class="ac-tools">Tools: ${a.tool_names.map(t => escapeHtml(t)).join(', ')}</div>` : ''}
            </div>
        `).join('');
    } catch {
        showToast('error', 'Failed to load agent registry');
    }
}

/* ----------------------------------------
   Toast
   ---------------------------------------- */
function showToast(type, message) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const icons = { success: 'fa-check-circle', info: 'fa-info-circle', warning: 'fa-exclamation-triangle', error: 'fa-times-circle' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<i class="fas ${icons[type]}"></i> ${escapeHtml(message)}`;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

/* ========================================
   CONFIGURATION PAGE
   ======================================== */
let configLoaded = {};

async function loadConfig() {
    // Init tab clicks
    document.querySelectorAll('.config-tab').forEach(tab => {
        tab.onclick = () => {
            document.querySelectorAll('.config-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.config-panel').forEach(p => p.classList.add('hidden'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.remove('hidden');
            loadConfigTab(tab.dataset.tab);
        };
    });
    loadConfigTab('cfg-agents');
}

async function loadConfigTab(tabId) {
    if (configLoaded[tabId]) return;
    try {
        switch (tabId) {
            case 'cfg-agents': {
                const res = await fetch(`${API_BASE}/api/config/agents`);
                const data = await res.json();
                renderCfgAgents(data.agents || data || []);
                break;
            }
            case 'cfg-symptoms': {
                const res = await fetch(`${API_BASE}/api/config/symptoms`);
                const data = await res.json();
                renderCfgSymptoms(data.items || data || []);
                break;
            }
            case 'cfg-hypotheses': {
                const res = await fetch(`${API_BASE}/api/config/hypotheses`);
                const data = await res.json();
                renderCfgHypotheses(data.items || data || []);
                break;
            }
            case 'cfg-evidence': {
                const res = await fetch(`${API_BASE}/api/config/evidence`);
                const data = await res.json();
                renderCfgEvidence(data.items || data || []);
                break;
            }
            case 'cfg-actions': {
                const res = await fetch(`${API_BASE}/api/config/actions`);
                const data = await res.json();
                renderCfgActions(data.items || data || []);
                break;
            }
            case 'cfg-knowledge': {
                const res = await fetch(`${API_BASE}/api/config/knowledge`);
                const data = await res.json();
                renderCfgKnowledge(data.files || data || []);
                break;
            }
            case 'cfg-customers': {
                const res = await fetch(`${API_BASE}/api/config/customers`);
                const data = await res.json();
                renderCfgCustomers(data);
                break;
            }
            case 'cfg-channels': {
                const res = await fetch(`${API_BASE}/api/config/channels`);
                const data = await res.json();
                renderCfgChannels(data);
                break;
            }
        }
        configLoaded[tabId] = true;
    } catch {
        showToast('error', `Failed to load ${tabId.replace('cfg-', '')}`);
    }
}

/* --- Config: Agents --- */
const AGENT_ICONS = {
    orchestrator: 'fa-chess-king', triage: 'fa-filter', hypothesis_selector: 'fa-lightbulb',
    evidence_planner: 'fa-clipboard-list', evidence_collector: 'fa-search', reasoner: 'fa-brain',
    action_planner: 'fa-tasks', notification: 'fa-bell'
};

function renderCfgAgents(agents) {
    const el = document.getElementById('cfg-agents');
    el.innerHTML = `<div class="cfg-agent-grid">${agents.map(a => {
        const role = a.role || '';
        const icon = AGENT_ICONS[role] || 'fa-robot';
        const model = a.model || '';
        const temp = a.temperature ?? '';
        const tags = a.technology_tags || [];
        const tools = a.tool_names || [];
        const objective = (a.objective || '').trim().substring(0, 200);
        return `<div class="cfg-agent-card">
            <div class="cfg-agent-top">
                <div class="cfg-agent-avatar ${escapeHtml(role)}"><i class="fas ${icon}"></i></div>
                <div class="cfg-agent-identity">
                    <h4>${escapeHtml(a.display_name || a.name)}</h4>
                    <span class="cfg-role-badge">${escapeHtml(role)}</span>
                </div>
            </div>
            <div class="cfg-agent-body">
                <div class="cfg-desc">${escapeHtml(a.description || '')}</div>
                ${objective ? `<div class="cfg-label">Objective</div><div class="cfg-objective">${escapeHtml(objective)}</div>` : ''}
                <div class="cfg-label">Model &amp; Tags</div>
                <div class="cfg-tags">
                    <span class="cfg-tag model">${escapeHtml(model)}${temp !== '' ? ` · temp ${temp}` : ''}</span>
                    ${tags.map(t => `<span class="cfg-tag">${escapeHtml(t)}</span>`).join('')}
                </div>
                ${tools.length ? `<div class="cfg-label">Tools (${tools.length})</div>
                <div class="cfg-tools-list">${tools.map(t => `<span class="cfg-tool-pill">${escapeHtml(t)}</span>`).join('')}</div>` : ''}
            </div>
        </div>`;
    }).join('')}</div>`;
}

/* --- Config: Symptoms --- */
function renderCfgSymptoms(symptoms) {
    const el = document.getElementById('cfg-symptoms');
    el.innerHTML = `<div class="cfg-table-wrap"><table class="cfg-table">
        <thead><tr>
            <th>ID</th><th>Name</th><th>Category</th><th>Template</th><th>Extracted When</th><th>Filters</th>
        </tr></thead>
        <tbody>${symptoms.map(s => {
            const filters = s.filters || {};
            const filterHtml = typeof filters === 'object' && !Array.isArray(filters)
                ? Object.entries(filters).map(([k,v]) => `<span class="td-badge filter">${escapeHtml(k)}: ${escapeHtml(String(v))}</span>`).join(' ')
                : Array.isArray(filters) ? filters.map(f => `<span class="td-badge filter">${escapeHtml(typeof f === 'string' ? f : JSON.stringify(f))}</span>`).join(' ')
                : '';
            return `<tr>
                <td class="td-id">${escapeHtml(s.id)}</td>
                <td>${escapeHtml(s.name || '')}</td>
                <td><span class="td-badge cat">${escapeHtml(s.category || '')}</span></td>
                <td class="td-template">${escapeHtml(s.template || '')}</td>
                <td>${escapeHtml(s.extracted_when || '')}</td>
                <td class="td-tags">${filterHtml || '<span style="color:var(--text-muted)">—</span>'}</td>
            </tr>`;
        }).join('')}</tbody>
    </table></div>`;
}

/* --- Config: Hypotheses --- */
function renderCfgHypotheses(hypotheses) {
    const el = document.getElementById('cfg-hypotheses');
    el.innerHTML = `<div class="cfg-table-wrap"><table class="cfg-table">
        <thead><tr>
            <th>ID</th><th>Name</th><th>Category</th><th>Statement</th><th>Applicable Symptoms</th><th>Evidence Needed</th>
        </tr></thead>
        <tbody>${hypotheses.map(h => `<tr>
            <td class="td-id">${escapeHtml(h.id)}</td>
            <td><strong>${escapeHtml(h.name || '')}</strong></td>
            <td><span class="td-badge cat">${escapeHtml(h.category || '')}</span></td>
            <td class="td-template">${escapeHtml(h.statement || h.template || '')}</td>
            <td class="td-tags">${(h.applicable_symptoms || []).map(s => `<span class="td-badge tag">${escapeHtml(s)}</span>`).join(' ')}</td>
            <td class="td-tags">${(h.evidence_needed || []).map(e => `<span class="td-badge filter">${escapeHtml(e)}</span>`).join(' ')}</td>
        </tr>`).join('')}</tbody>
    </table></div>`;
}

/* --- Config: Evidence --- */
function renderCfgEvidence(evidence) {
    const el = document.getElementById('cfg-evidence');
    el.innerHTML = `<div class="cfg-table-wrap"><table class="cfg-table">
        <thead><tr>
            <th>ID</th><th>Description</th><th>Tech Tag</th><th>Tool</th><th>Parameters</th>
        </tr></thead>
        <tbody>${evidence.map(e => {
            const params = e.parameters ? Object.entries(e.parameters).map(([k,v]) =>
                `<span class="td-badge filter">${escapeHtml(k)}=${escapeHtml(String(v))}</span>`
            ).join(' ') : '';
            return `<tr>
                <td class="td-id">${escapeHtml(e.id)}</td>
                <td>${escapeHtml(e.description || '')}</td>
                <td><span class="td-badge tag">${escapeHtml(e.technology_tag || '')}</span></td>
                <td><span class="cfg-tool-pill">${escapeHtml(e.tool_name || e.tool || '')}</span></td>
                <td class="td-tags">${params}</td>
            </tr>`;
        }).join('')}</tbody>
    </table></div>`;
}

/* --- Config: Actions --- */
function renderCfgActions(actions) {
    const el = document.getElementById('cfg-actions');
    el.innerHTML = `<div class="cfg-table-wrap"><table class="cfg-table">
        <thead><tr>
            <th>ID</th><th>Name</th><th>Type</th><th>Tier</th><th>Hypotheses</th><th>Tool</th>
        </tr></thead>
        <tbody>${actions.map(a => {
            const tierClass = a.tier === 'auto' ? 'auto' : 'gated';
            const tierIcon = a.tier === 'auto' ? '⚡' : '🔒';
            const hypotheses = (a.applicable_hypotheses || []).map(h => `<span class="td-badge tag">${escapeHtml(h)}</span>`).join(' ');
            return `<tr>
                <td class="td-id">${escapeHtml(a.id)}</td>
                <td>${escapeHtml(a.name || a.display_name || '')}<br><span style="font-size:10px;color:var(--text-muted)">${escapeHtml(a.description || '')}</span></td>
                <td><span class="td-badge cat">${escapeHtml(a.type || '')}</span></td>
                <td><span class="td-badge ${tierClass}">${tierIcon} ${escapeHtml(a.tier || '')}</span></td>
                <td class="td-tags">${hypotheses}</td>
                <td><span class="cfg-tool-pill">${escapeHtml(a.tool || '')}</span></td>
            </tr>`;
        }).join('')}</tbody>
    </table></div>`;
}

/* --- Config: Knowledge --- */
function renderCfgKnowledge(files) {
    const el = document.getElementById('cfg-knowledge');
    const icons = {
        'evidence_evaluation_matrix': 'fa-balance-scale',
        'confidence_scoring': 'fa-calculator',
        'customer_health_reasoning': 'fa-heartbeat',
        'sli_interpretation': 'fa-chart-line',
        'timing_correlation': 'fa-clock',
        'cross_evidence_patterns': 'fa-project-diagram',
    };
    el.innerHTML = `<div class="cfg-knowledge-grid">${files.map(k => {
        const stem = (k.name || '').replace('.md', '');
        const icon = icons[stem] || 'fa-file-alt';
        const preview = (k.preview || k.content || '').substring(0, 120).replace(/[#\n]/g, ' ').trim();
        const sizeStr = k.size ? (typeof k.size === 'number' ? `${(k.size / 1024).toFixed(1)} KB` : k.size) : '';
        return `<div class="cfg-knowledge-card" onclick="showCfgKnowledgeDetail('${escapeHtml(k.name)}')">
            <div class="kc-icon"><i class="fas ${icon}"></i></div>
            <div class="kc-title">${escapeHtml(k.title || k.name)}</div>
            <div class="kc-desc">${escapeHtml(preview)}...</div>
            <div class="kc-size">${escapeHtml(k.name)} ${sizeStr ? '· ' + sizeStr : ''}</div>
        </div>`;
    }).join('')}</div>`;
}

async function showCfgKnowledgeDetail(name) {
    try {
        const res = await fetch(`${API_BASE}/api/config/knowledge/${encodeURIComponent(name)}`);
        const k = await res.json();
        const el = document.getElementById('cfg-knowledge');
        const existing = el.querySelector('.cfg-knowledge-detail');
        if (existing) existing.remove();
        const detail = document.createElement('div');
        detail.className = 'cfg-knowledge-detail';
        detail.style.cssText = 'margin-top:16px; border:1px solid var(--border); border-radius:10px; overflow:hidden;';
        detail.innerHTML = `
            <div style="padding:12px 16px; background:linear-gradient(135deg,#1b1f3b,#272b4d); color:white; display:flex; justify-content:space-between; align-items:center;">
                <h4 style="font-size:14px;">${escapeHtml(k.title || k.name)}</h4>
                <button onclick="this.closest('.cfg-knowledge-detail').remove()" style="border:none;background:none;color:rgba(255,255,255,0.6);cursor:pointer;font-size:16px;padding:4px 8px;">✕</button>
            </div>
            <div style="padding:20px; font-size:13px; line-height:1.7; color:var(--text-secondary); max-height:400px; overflow-y:auto; white-space:pre-wrap;">${escapeHtml(k.content || '')}</div>
        `;
        el.appendChild(detail);
        detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
        showToast('error', 'Failed to load knowledge file');
    }
}

/* --- Config: Customers --- */
function renderCfgCustomers(data) {
    const el = document.getElementById('cfg-customers');
    const cust = data.customer || {};
    const resources = cust.resources || [];
    const subs = cust.subscription_ids || [];
    const patterns = cust.resource_group_patterns || [];
    el.innerHTML = `<div class="cfg-customer-panel">
        <div class="cfg-cust-info">
            <h3>${escapeHtml(cust.name || 'N/A')}</h3>
            <div class="cfg-cust-id">${escapeHtml(cust.customer_id || '')}</div>
            <div class="cfg-label">Subscriptions</div>
            ${subs.map(s => `<div class="cfg-cust-detail"><span class="cfg-tool-pill">${escapeHtml(s)}</span></div>`).join('')}
            <div class="cfg-label">Resource Group Patterns</div>
            ${patterns.map(p => `<div class="cfg-cust-detail"><span class="cfg-tool-pill">${escapeHtml(p)}</span></div>`).join('')}
        </div>
        <div>
            <div class="cfg-label" style="margin-bottom:8px;">Registered Resources (${resources.length})</div>
            <div class="cfg-table-wrap"><table class="cfg-table">
                <thead><tr><th>Resource ID</th><th>Service</th><th>Region</th><th>Resource Group</th></tr></thead>
                <tbody>${resources.map(r => `<tr>
                    <td class="td-id">${escapeHtml(r.resource_id)}</td>
                    <td><span class="td-badge tag">${escapeHtml(r.service)}</span></td>
                    <td>${escapeHtml(r.region)}</td>
                    <td><span class="cfg-tool-pill">${escapeHtml(r.resource_group)}</span></td>
                </tr>`).join('')}</tbody>
            </table></div>
        </div>
    </div>`;
}

/* --- Config: Channels --- */
function renderCfgChannels(data) {
    const el = document.getElementById('cfg-channels');
    const channels = data.channels || [];
    const contacts = data.contacts || [];
    const channelIcons = { teams_webhook: 'teams', smtp: 'email', icm_api: 'icm', webhook: 'webhook', teams: 'teams', email: 'email' };
    const channelFA = { teams_webhook: 'fa-comments', smtp: 'fa-envelope', icm_api: 'fa-ticket-alt', webhook: 'fa-plug', teams: 'fa-comments', email: 'fa-envelope' };

    let html = `<div class="cfg-label" style="margin-bottom:12px;">Notification Channels (${channels.length})</div>
    <div class="cfg-channels-grid">${channels.map(ch => {
        const t = ch.type || '';
        const iconCls = channelIcons[t] || 'webhook';
        const iconFA = channelFA[t] || 'fa-plug';
        return `<div class="cfg-channel-card">
            <div class="cfg-channel-icon ${iconCls}"><i class="fas ${iconFA}"></i></div>
            <div class="cfg-channel-body">
                <h4>${escapeHtml(ch.name || ch.display_name || '')}</h4>
                <div class="cfg-channel-type">${escapeHtml(t)}</div>
                ${ch.config_key ? `<div class="cfg-channel-env"><span class="cfg-tool-pill">${escapeHtml(ch.config_key)}</span></div>` : ''}
            </div>
        </div>`;
    }).join('')}</div>`;

    if (contacts.length) {
        html += `<div class="cfg-label" style="margin-top:24px; margin-bottom:12px;">Customer Contacts (${contacts.length})</div>
        <div class="cfg-table-wrap"><table class="cfg-table">
            <thead><tr><th>Customer</th><th>TAM</th><th>TAM Email</th><th>Account Team</th></tr></thead>
            <tbody>${contacts.map(c => {
                const rawTeam = c.account_team || [];
                const team = typeof rawTeam === 'string' ? escapeHtml(rawTeam) : Array.isArray(rawTeam) ? rawTeam.map(m => escapeHtml(typeof m === 'string' ? m : m.name || '')).join(', ') : '';
                return `<tr>
                    <td><strong>${escapeHtml(c.customer || '')}</strong><br><span class="td-id">${escapeHtml(c.customer_id || '')}</span></td>
                    <td>${escapeHtml(c.tam || '')}</td>
                    <td><span class="cfg-tool-pill">${escapeHtml(c.tam_email || '')}</span></td>
                    <td>${team || '—'}</td>
                </tr>`;
            }).join('')}</tbody>
        </table></div>`;
    }

    el.innerHTML = html;
}

/* ========================================
   DATA FILES PAGE
   ======================================== */
async function loadDataFiles() {
    try {
        const res = await fetch(`${API_BASE}/api/datafiles`);
        const data = await res.json();
        const files = data.files || data || [];
        const grid = document.getElementById('datafilesGrid');
        grid.innerHTML = files.map(f => `
            <div class="df-card" onclick="previewDataFile('${escapeHtml(f.path || f.name)}')">
                <div class="df-icon"><i class="fas fa-table"></i></div>
                <div class="df-name">${escapeHtml(f.name)}</div>
                <div class="df-stats">${f.record_count || 0} records · ${(f.columns || []).length} columns${f.size ? ' · ' + f.size : ''}</div>
                <div class="df-cols">${(f.columns || []).slice(0, 8).map(c => `<span class="df-col-tag">${escapeHtml(c)}</span>`).join('')}${(f.columns || []).length > 8 ? `<span class="df-col-tag">+${(f.columns || []).length - 8} more</span>` : ''}</div>
            </div>
        `).join('');
    } catch {
        showToast('error', 'Failed to load data files');
    }
}

async function previewDataFile(path) {
    try {
        const res = await fetch(`${API_BASE}/api/datafiles/${encodeURIComponent(path)}`);
        const data = await res.json();
        const preview = document.getElementById('datafilePreview');
        preview.classList.remove('hidden');
        document.getElementById('dfPreviewTitle').textContent = `${data.name || path} — Preview (first 20 rows)`;

        const records = data.records || [];
        if (!records.length) {
            document.getElementById('dfPreviewTable').innerHTML = '<p style="padding:16px;color:var(--text-muted);">No data</p>';
            return;
        }
        const cols = Object.keys(records[0]);
        const rows = records.slice(0, 20);
        document.getElementById('dfPreviewTable').innerHTML = `<table>
            <thead><tr>${cols.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
            <tbody>${rows.map(r => `<tr>${cols.map(c => `<td title="${escapeHtml(String(r[c] ?? ''))}">${escapeHtml(String(r[c] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
        </table>`;
        preview.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
        showToast('error', 'Failed to load file preview');
    }
}

/* ========================================
   KNOWLEDGE PAGE
   ======================================== */
let knowledgeCache = null;

async function loadKnowledge() {
    if (knowledgeCache) { renderKnowledgePage(knowledgeCache); return; }
    try {
        const res = await fetch(`${API_BASE}/api/knowledge`);
        const data = await res.json();
        knowledgeCache = data.files || data || [];
        renderKnowledgePage(knowledgeCache);
    } catch {
        showToast('error', 'Failed to load knowledge files');
    }
}

function renderKnowledgePage(files) {
    const icons = {
        'evidence_evaluation_matrix': 'fa-balance-scale',
        'confidence_scoring': 'fa-calculator',
        'customer_health_reasoning': 'fa-heartbeat',
        'sli_interpretation': 'fa-chart-line',
        'timing_correlation': 'fa-clock',
        'cross_evidence_patterns': 'fa-project-diagram',
    };
    const grid = document.getElementById('knowledgeGrid');
    grid.innerHTML = files.map(k => {
        const stem = (k.name || '').replace('.md', '');
        const icon = icons[stem] || 'fa-file-alt';
        const preview = (k.preview || '').substring(0, 150).replace(/[#\n]/g, ' ').trim();
        const sizeStr = k.size ? (typeof k.size === 'number' ? `${(k.size / 1024).toFixed(1)} KB` : k.size) : '';
        return `<div class="cfg-knowledge-card" onclick="showKnowledgeFile('${escapeHtml(k.name)}')">
            <div class="kc-icon"><i class="fas ${icon}"></i></div>
            <div class="kc-title">${escapeHtml(k.title || k.name)}</div>
            <div class="kc-desc">${escapeHtml(preview)}...</div>
            <div class="kc-size">${escapeHtml(k.name)} ${sizeStr ? '· ' + sizeStr : ''}</div>
        </div>`;
    }).join('');
}

async function showKnowledgeFile(name) {
    try {
        const res = await fetch(`${API_BASE}/api/knowledge/${encodeURIComponent(name)}`);
        const k = await res.json();
        const viewer = document.getElementById('knowledgeViewer');
        viewer.classList.remove('hidden');
        document.getElementById('kvTitle').textContent = k.title || k.name;
        document.getElementById('kvContent').textContent = k.content || '';
        viewer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
        showToast('error', 'Failed to load knowledge file');
    }
}

/* ----------------------------------------
   Utilities
   ---------------------------------------- */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text || '');
    return div.innerHTML;
}

function timeAgo(timestamp) {
    const now = new Date();
    const then = new Date(timestamp);
    const diff = Math.floor((now - then) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff/60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)} hours ago`;
    return `${Math.floor(diff/86400)} days ago`;
}
