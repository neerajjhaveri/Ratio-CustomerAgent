import { useEffect, useState, useRef, useCallback, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { listScenarios, getScenario, streamInvestigation, type Scenario, type InvestigationEvent } from '../../api/customerAgentClient';

const PHASES = ['initializing', 'triage', 'hypothesizing', 'planning', 'collecting', 'reasoning', 'acting', 'notifying', 'complete'];

const PHASE_COLORS: Record<string, string> = {
  initializing: '#17a2b8',
  triage: '#0984e3',
  hypothesizing: '#e17055',
  planning: '#fdcb6e',
  collecting: '#00b894',
  reasoning: '#d63031',
  acting: '#e84393',
  notifying: '#6c5ce7',
  complete: '#28a745',
};

interface ParsedState {
  signals: Record<string, unknown>[];
  symptoms: Record<string, unknown>[];
  hypotheses: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  actions: Record<string, unknown>[];
  report?: Record<string, unknown>;
}

function parseStructuredData(events: InvestigationEvent[]): ParsedState {
  const state: ParsedState = { signals: [], symptoms: [], hypotheses: [], evidence: [], actions: [] };

  // Helper: try to extract JSON from content text
  const extractJson = (content: string): Record<string, unknown> | null => {
    const match = content.match(/```json\s*([\s\S]*?)```/);
    if (match) {
      try { return JSON.parse(match[1]); } catch { /* ignore */ }
    }
    // Try parsing the whole content as JSON
    try { return JSON.parse(content); } catch { return null; }
  };

  for (const evt of events) {
    const d = evt.data || {};

    // Signals from phase_change events
    if (d.signals && Array.isArray(d.signals)) state.signals = d.signals as Record<string, unknown>[];

    // Try structured_output from event data first
    let so = d.structured_output as Record<string, unknown> | undefined;

    // If no structured_output in data, try extracting from content
    if (!so && evt.content) {
      const parsed = extractJson(evt.content);
      if (parsed?.structured_output) {
        so = parsed.structured_output as Record<string, unknown>;
      } else if (parsed) {
        so = parsed;
      }
    }

    if (so) {
      // Symptoms
      if (so.symptoms && Array.isArray(so.symptoms)) {
        for (const s of so.symptoms as Record<string, unknown>[]) {
          if (!state.symptoms.find(x => x.id === s.id)) state.symptoms.push(s);
        }
      }
      // Hypotheses — always replace with latest
      if (so.hypotheses && Array.isArray(so.hypotheses)) {
        state.hypotheses = so.hypotheses as Record<string, unknown>[];
      }
      // Evidence
      if (so.evidence_analyzed && Array.isArray(so.evidence_analyzed)) {
        for (const e of so.evidence_analyzed as Record<string, unknown>[]) {
          if (!state.evidence.find(x => x.recommendation_id === e.recommendation_id)) state.evidence.push(e);
        }
      }
      // Hypothesis verdicts — update confidence
      if (so.hypothesis_verdicts && Array.isArray(so.hypothesis_verdicts)) {
        for (const v of so.hypothesis_verdicts as Record<string, unknown>[]) {
          const hyp = state.hypotheses.find(h => h.id === v.hypothesis_id);
          if (hyp) {
            hyp.verdict = v.verdict;
            hyp.reasoning = v.reasoning;
            if (String(v.verdict).includes('SUPPORT')) hyp.confidence = 0.95;
            else if (String(v.verdict).includes('UNSUPPORT')) hyp.confidence = 0;
          }
        }
      }
      // Actions
      if (so.actions && Array.isArray(so.actions)) {
        state.actions = so.actions as Record<string, unknown>[];
      }
      // Report (from notification agent)
      if (so.report) {
        state.report = so.report as Record<string, unknown>;
      }
    }
  }
  return state;
}

function SidebarSection({ icon, label, count, children }: { icon: string; label: string; count: number; color?: string; children: ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="cha-inv-section">
      <div className="cha-inv-section-title" onClick={() => setOpen(o => !o)} style={{ cursor: 'pointer', userSelect: 'none' }}>
        <i className={`fas ${icon}`} /> {label} <span className="count">{count}</span>
        <i className={`fas fa-chevron-${open ? 'down' : 'right'}`} style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--cha-text-muted)', transition: '0.2s ease' }} />
      </div>
      {open && (
        <div className="cha-inv-section-body" style={{ maxHeight: 200, overflowY: 'auto' }}>
          {count === 0 ? <div className="cha-inv-item" style={{ color: 'var(--cha-text-muted)' }}>Waiting…</div> : children}
        </div>
      )}
    </div>
  );
}

export default function ChaActivePage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [events, setEvents] = useState<InvestigationEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [currentPhase, setCurrentPhase] = useState('');
  const [tickCount, setTickCount] = useState(0);
  const [activeView, setActiveView] = useState<'stream' | 'graph' | 'flow'>('stream');
  const streamRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const navigate = useNavigate();

  // Load scenarios
  useEffect(() => {
    listScenarios().then(s => {
      setScenarios(s);
      if (s.length > 0) setSelectedId(s[0].id);
    }).catch(() => {});
  }, []);

  // Check if a scenario was queued from the Scenarios page
  useEffect(() => {
    const queued = sessionStorage.getItem('cha-run-scenario');
    if (queued) {
      sessionStorage.removeItem('cha-run-scenario');
      setSelectedId(queued);
      getScenario(queued).then(s => {
        setScenario(s);
        setSelectedId(s.id);
      }).catch(() => {});
    }
  }, []);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: 'smooth' });
  }, [events]);

  const stopInvestigation = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const runInvestigation = useCallback(async (scenarioId: string) => {
    if (running) return;
    const s = scenarios.find(x => x.id === scenarioId);
    if (!s) {
      try { const fetched = await getScenario(scenarioId); setScenario(fetched); } catch { return; }
    } else {
      setScenario(s);
    }
    setRunning(true);
    setDone(false);
    setEvents([]);
    setCurrentPhase('initializing');
    setTickCount(0);

    // Create a new AbortController for this run
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let tick = 0;
      for await (const evt of streamInvestigation(scenarioId, controller.signal)) {
        if (evt.event_type === 'done') break;
        tick++;
        setTickCount(tick);
        setEvents(prev => [...prev, evt]);
        if (evt.phase) setCurrentPhase(evt.phase);
      }
      setDone(true);
      setCurrentPhase('complete');
    } catch (err: unknown) {
      // Don't show an error if the stream was intentionally aborted
      if (err instanceof Error && err.name === 'AbortError') {
        setDone(true);
      } else {
        setEvents(prev => [...prev, { event_type: 'error', agent_name: '', phase: '', content: String(err), data: {}, timestamp: new Date().toISOString() }]);
      }
    } finally {
      setRunning(false);
    }
  }, [running, scenarios]);

  // Auto-run queued scenario
  useEffect(() => {
    if (scenario && !running && events.length === 0 && !done) {
      runInvestigation(scenario.id);
    }
  }, [scenario]); // eslint-disable-line react-hooks/exhaustive-deps

  const phaseIdx = PHASES.indexOf(currentPhase);
  const parsed = parseStructuredData(events);

  // Check if content has JSON and mark it
  const hasJson = (content: string) => content.includes('"structured_output"') || content.includes('"assessment"') || content.includes('"decision"');

  // Pre-investigation state: show scenario picker
  if (!scenario && !running) {
    return (
      <>
        {/* Scenario selector */}
        <div style={{ maxWidth: 600, margin: '40px auto', textAlign: 'center' }}>
          <div className="cha-empty-state" style={{ padding: '30px 20px' }}>
            <i className="fas fa-flask" />
            <h3>Active Investigation</h3>
            <p>Select a scenario and click Run to start an investigation.</p>
          </div>
          <select
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
            style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid var(--cha-border)', fontSize: 14, marginBottom: 12 }}
          >
            {scenarios.map(s => (
              <option key={s.id} value={s.id}>{s.name} ({s.id})</option>
            ))}
          </select>
          <button className="cha-btn-primary" style={{ width: '100%', padding: '12px 20px', fontSize: 15 }} onClick={() => {
            if (selectedId) runInvestigation(selectedId);
          }}>
            <i className="fas fa-play" /> Run Scenario
          </button>
        </div>

        {/* Quick cards */}
        <div className="cha-card-grid" style={{ marginTop: 24 }}>
          {scenarios.slice(0, 6).map(s => (
            <div key={s.id} className="cha-scenario-card" onClick={() => { setSelectedId(s.id); runInvestigation(s.id); }}>
              <div className="cha-sc-header">
                <span className="cha-sc-id">{s.id}</span>
              </div>
              <div className="cha-sc-name">{s.name}</div>
              <div className="cha-sc-desc">{s.description.slice(0, 100)}…</div>
              <div className="cha-sc-meta">
                <span className="cha-sc-tag">{s.category}</span>
                <span className="cha-sc-tag">{s.signal_count} signal{s.signal_count !== 1 ? 's' : ''}</span>
              </div>
            </div>
          ))}
        </div>
      </>
    );
  }

  const sc = scenario!;

  return (
    <>
      {/* Investigation header */}
      <div className="cha-investigation-header">
        <h3>{sc.name}</h3>
        <div className="subtitle">{sc.description}</div>
        <div className="meta">
          <span><i className="fas fa-hashtag" /> {sc.id}</span>
          <span><i className="fas fa-layer-group" /> {sc.category}</span>
          <span><i className="fas fa-signal" /> {sc.signal_count} signal{sc.signal_count !== 1 ? 's' : ''}</span>
          {running && (
            <button
              className="cha-btn-run"
              style={{ marginLeft: 'auto', background: 'var(--cha-danger)', color: '#fff' }}
              onClick={stopInvestigation}
              title="Stop investigation"
            >
              <i className="fas fa-stop" /> Stop
            </button>
          )}
        </div>
      </div>

      {/* Expected outcome */}
      <div className="cha-expected-panel">
        <div style={{ marginBottom: 6 }}>
          <strong>Expected Outcome: </strong>{sc.expected_outcome}
        </div>
        <div>
          <strong>Expected Root Cause: </strong>{sc.expected_root_cause}
        </div>
      </div>

      {/* Phase progress */}
      <div className="cha-phase-bar">
        {PHASES.map((p, i) => (
          <div
            key={p}
            className={`cha-phase-step${i < phaseIdx ? ' done' : i === phaseIdx ? ' active' : ''}`}
            title={p}
            style={i < phaseIdx ? { background: PHASE_COLORS[PHASES[i]] || 'var(--cha-success)' } : undefined}
          />
        ))}
      </div>

      {/* View toggle */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 12, background: 'var(--cha-bg-main)', padding: 3, borderRadius: 6, width: 'fit-content' }}>
        {(['stream', 'graph', 'flow'] as const).map(v => (
          <button key={v} className="cha-btn-run" onClick={() => setActiveView(v)} style={{
            background: activeView === v ? 'var(--cha-bg-white)' : 'transparent',
            color: activeView === v ? 'var(--cha-primary)' : 'var(--cha-text-muted)',
            boxShadow: activeView === v ? 'var(--cha-shadow-sm)' : 'none',
          }}>
            <i className={`fas ${v === 'stream' ? 'fa-stream' : v === 'graph' ? 'fa-project-diagram' : 'fa-route'}`} />
            {v === 'stream' ? ' Stream View' : v === 'graph' ? ' Relationship Graph' : ' Agent Flow'}
          </button>
        ))}
      </div>

      {/* ═══ STREAM VIEW ═══ */}
      {activeView === 'stream' && (
        <div className="cha-inv-layout">
          <div className="cha-stream-container">
            <div className="cha-stream-header">
              <span><i className="fas fa-stream" /> Agent Activity Stream</span>
              <span style={{ fontFamily: 'monospace', color: 'var(--cha-primary)' }}>Tick: {tickCount}</span>
            </div>
            <div className="cha-stream-body" ref={streamRef}>
              {events.map((evt, i) => {
                const phaseColor = PHASE_COLORS[evt.phase] || 'var(--cha-primary)';
                return (
                  <div key={i} className={`cha-stream-event ${evt.event_type}`}>
                    <div className="se-header">
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className="se-agent">{evt.agent_name || evt.event_type.replace(/_/g, ' ')}</span>
                        {evt.phase && <span className="se-phase" style={{ background: phaseColor, color: 'white' }}>{evt.phase}</span>}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {hasJson(evt.content) && <span style={{ fontSize: 9, color: 'var(--cha-success)', fontWeight: 600 }}>JSON ✓</span>}
                        <span className="se-time">#{i + 1}</span>
                      </span>
                    </div>
                    <div className="se-body">{evt.content}</div>
                  </div>
                );
              })}
              {running && (
                <div className="cha-stream-event" style={{ borderLeftColor: 'var(--cha-primary)', textAlign: 'center', color: 'var(--cha-primary)' }}>
                  <i className="fas fa-spinner fa-spin" /> Investigation in progress…
                </div>
              )}
            </div>
          </div>

          {/* Right: Investigation state sidebar */}
          <div className="cha-inv-sidebar">
            <SidebarSection icon="fa-signal" label="Signals" count={parsed.signals.length} color="#6c5ce7">
              {parsed.signals.map((s, i) => (
                <div key={i} className="cha-inv-item">
                  <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#6c5ce7', fontSize: 10 }}>{String(s.signal_type || s.sli_id || '')}</span>
                  {' '}{String(s.description || `${s.resource} — ${s.metric_type || ''}`)}
                </div>
              ))}
            </SidebarSection>
            <SidebarSection icon="fa-stethoscope" label="Symptoms" count={parsed.symptoms.length} color="#0984e3">
              {parsed.symptoms.map((s, i) => (
                <div key={i} className="cha-inv-item">
                  <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#0984e3', fontSize: 10 }}>{String(s.id || `SYM-${i + 1}`)}</span>
                  {' '}{String(s.text || s.description || s.name || '')}
                </div>
              ))}
            </SidebarSection>
            <SidebarSection icon="fa-lightbulb" label="Hypotheses" count={parsed.hypotheses.length} color="#e17055">
              {parsed.hypotheses.map((h, i) => {
                const conf = Math.round(Number(h.confidence || 0) * 100);
                const verdict = String(h.verdict || h.status || h.initial_plausibility || 'ACTIVE');
                const isConfirmed = verdict.includes('SUPPORT') || verdict.includes('confirmed') || conf >= 85;
                const isRefuted = verdict.includes('REFUT') || verdict.includes('refuted');
                const confColor = isConfirmed ? '#28a745' : isRefuted ? '#dc3545' : '#4f6bed';
                const label = isConfirmed ? 'confirmed' : isRefuted ? 'refuted' : verdict.toLowerCase();
                return (
                  <div key={i} className="cha-inv-item" style={{ paddingBottom: 8, marginBottom: 6, borderBottom: '1px solid #f0f0f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                      <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#e17055', fontSize: 10 }}>{String(h.id || `HYP-${i + 1}`)}</span>
                      <span style={{ fontWeight: 600, color: confColor, fontSize: 10 }}>{conf}% {label}</span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--cha-text-secondary)', marginBottom: 4 }}>{String(h.statement || h.description || h.name || '')}</div>
                    {conf > 0 && (
                      <div style={{ height: 4, borderRadius: 2, background: '#e8e8e8', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${conf}%`, background: confColor, borderRadius: 2, transition: 'width 0.5s ease' }} />
                      </div>
                    )}
                  </div>
                );
              })}
            </SidebarSection>
            <SidebarSection icon="fa-search" label="Evidence" count={parsed.evidence.length} color="#00b894">
              {parsed.evidence.map((e, i) => (
                <div key={i} className="cha-inv-item" style={{ paddingBottom: 6, marginBottom: 4 }}>
                  <div style={{ fontFamily: 'monospace', fontWeight: 600, color: '#00b894', fontSize: 10 }}>{String(e.recommendation_id || e.id || e.agent || `ER-${i + 1}`)}</div>
                  <div style={{ fontSize: 11, color: 'var(--cha-text-secondary)' }}>{String(e.summary || e.description || e.content || e.relevance || '')}</div>
                </div>
              ))}
            </SidebarSection>
            <SidebarSection icon="fa-bolt" label="Actions" count={parsed.actions.length} color="#e84393">
              {parsed.actions.map((a, i) => (
                <div key={i} className="cha-inv-item" style={{ display: 'flex', alignItems: 'flex-start', gap: 6, paddingBottom: 4 }}>
                  <span style={{ color: '#e84393', fontSize: 12, flexShrink: 0 }}>⚡</span>
                  <div>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#e84393', fontSize: 10 }}>{String(a.action_id || a.name || '')}</span>
                    {' '}<span style={{ fontSize: 11, color: 'var(--cha-text-secondary)' }}>{String(a.display_name || a.description || '')}</span>
                    {a.tier ? <span style={{ fontWeight: 700, fontSize: 10 }}> — {String(a.tier)}</span> : null}
                  </div>
                </div>
              ))}
            </SidebarSection>
          </div>
        </div>
      )}

      {/* ═══ RELATIONSHIP GRAPH VIEW ═══ */}
      {activeView === 'graph' && (() => {
        // Card dimensions: each card is fixed-height for alignment
        const cardH = 76; // card height (padding + content)
        const cardGap = 10; // marginBottom between cards
        const nodeStep = cardH + cardGap; // total step per node
        const headerH = 30; // column header height
        const maxRows = Math.max(parsed.symptoms.length, parsed.hypotheses.length, parsed.evidence.length, 1);
        const svgH = maxRows * nodeStep + 20;
        // Center of card i relative to SVG (no header offset since SVG starts after spacer)
        const centerY = (i: number) => i * nodeStep + cardH / 2;

        return (
          <div style={{ border: '1px solid var(--cha-border)', borderRadius: 'var(--cha-radius-md)', overflow: 'hidden' }}>
            {/* Toolbar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', background: 'var(--cha-bg-main)', borderBottom: '1px solid var(--cha-border)' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--cha-text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <i className="fas fa-project-diagram" /> Investigation Relationship Graph
              </span>
              <div style={{ display: 'flex', gap: 12, fontSize: 10, color: 'var(--cha-text-muted)' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#0984e3', display: 'inline-block' }} />Symptom</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#e17055', display: 'inline-block' }} />Hypothesis</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#00b894', display: 'inline-block' }} />Evidence</span>
                <span style={{ color: 'var(--cha-border)' }}>|</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 16, height: 3, borderRadius: 2, background: '#28a745', display: 'inline-block' }} />Supports</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 16, height: 3, borderRadius: 2, background: '#dc3545', display: 'inline-block' }} />Refutes</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 16, height: 3, borderRadius: 2, background: '#f0ad4e', display: 'inline-block' }} />Partial</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 16, height: 3, borderRadius: 2, background: '#8a8aaa', display: 'inline-block' }} />Pending</span>
              </div>
            </div>
            {/* Graph with 3 columns and connector SVGs between them */}
            <div style={{ padding: 24, minHeight: 300 }}>
              <div style={{ display: 'flex', gap: 0, alignItems: 'flex-start' }}>
                {/* Symptoms column */}
                <div style={{ flex: 1, padding: '0 12px' }}>
                  <div style={{ height: headerH, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, color: '#0984e3', paddingBottom: 6, borderBottom: '2px solid #0984e3', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i className="fas fa-stethoscope" /> Symptoms
                  </div>
                  {parsed.symptoms.length > 0 ? parsed.symptoms.map((s, i) => (
                    <div key={i} style={{ height: cardH, border: '2px solid var(--cha-border)', borderLeft: '4px solid #0984e3', borderRadius: 8, padding: '10px 12px', marginBottom: cardGap, background: 'var(--cha-bg-white)', fontSize: 11, overflow: 'hidden', boxSizing: 'border-box' }}>
                      <div style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700, color: '#0984e3', marginBottom: 3 }}>{String(s.id || `SYM-${i + 1}`)}</div>
                      <div style={{ color: 'var(--cha-text-secondary)', lineHeight: 1.3 }}>{String(s.description || s.name || '').slice(0, 80)}</div>
                    </div>
                  )) : <div style={{ color: 'var(--cha-text-muted)', fontSize: 11, marginTop: 10 }}>No symptoms yet</div>}
                </div>

                {/* Connector SVG: Symptom → Hypothesis */}
                <div style={{ width: 40, flexShrink: 0 }}>
                  <div style={{ height: headerH }} />
                  <svg width="40" height={svgH} style={{ display: 'block' }}>
                    {parsed.symptoms.length > 0 && parsed.hypotheses.length > 0 &&
                      parsed.symptoms.map((_, si) =>
                        parsed.hypotheses.map((_, hi) => (
                          <path key={`s${si}h${hi}`}
                            d={`M 0,${centerY(si)} C 20,${centerY(si)} 20,${centerY(hi)} 40,${centerY(hi)}`}
                            fill="none" stroke="#0984e3" strokeWidth="2" opacity="0.4"
                          />
                        ))
                      )}
                  </svg>
                </div>

                {/* Hypotheses column */}
                <div style={{ flex: 1, padding: '0 12px' }}>
                  <div style={{ height: headerH, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, color: '#e17055', paddingBottom: 6, borderBottom: '2px solid #e17055', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i className="fas fa-lightbulb" /> Hypotheses
                  </div>
                  {parsed.hypotheses.length > 0 ? parsed.hypotheses.map((h, i) => {
                    const conf = Number(h.confidence || 0);
                    const verdict = String(h.verdict || h.status || 'active');
                    const badgeColor = verdict.includes('confirmed') ? '#28a745' : verdict.includes('refuted') ? '#dc3545' : '#17a2b8';
                    return (
                      <div key={i} style={{ height: cardH, border: '2px solid var(--cha-border)', borderLeft: '4px solid #e17055', borderRadius: 8, padding: '10px 12px', marginBottom: cardGap, background: 'var(--cha-bg-white)', fontSize: 11, position: 'relative', overflow: 'hidden', boxSizing: 'border-box' }}>
                        <span style={{ position: 'absolute', top: -8, right: 8, fontSize: 9, fontWeight: 700, padding: '1px 7px', borderRadius: 8, color: 'white', background: badgeColor }}>{verdict}</span>
                        <div style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700, color: '#e17055', marginBottom: 3 }}>{String(h.id || `HYP-${i + 1}`)}</div>
                        <div style={{ color: 'var(--cha-text-secondary)', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis' }}>{String(h.description || h.name || '').slice(0, 60)}</div>
                        <div style={{ fontSize: 10, fontWeight: 700, marginTop: 2, color: conf >= 0.85 ? '#28a745' : conf <= 0.1 ? '#dc3545' : '#f0ad4e' }}>{Math.round(conf * 100)}% confidence</div>
                      </div>
                    );
                  }) : <div style={{ color: 'var(--cha-text-muted)', fontSize: 11, marginTop: 10 }}>No hypotheses yet</div>}
                </div>

                {/* Connector SVG: Hypothesis → Evidence */}
                <div style={{ width: 40, flexShrink: 0 }}>
                  <div style={{ height: headerH }} />
                  <svg width="40" height={svgH} style={{ display: 'block' }}>
                    {parsed.hypotheses.length > 0 && parsed.evidence.length > 0 &&
                      parsed.hypotheses.map((_, hi) =>
                        parsed.evidence.map((e, ei) => {
                          const evVerdict = String(e.verdict || 'pending');
                          const color = evVerdict.includes('support') ? '#28a745' : evVerdict.includes('refut') ? '#dc3545' : '#8a8aaa';
                          const dash = evVerdict === 'pending' ? '4 3' : undefined;
                          return (
                            <path key={`h${hi}e${ei}`}
                              d={`M 0,${centerY(hi)} C 20,${centerY(hi)} 20,${centerY(ei)} 40,${centerY(ei)}`}
                              fill="none" stroke={color} strokeWidth="2" opacity="0.5" strokeDasharray={dash}
                            />
                          );
                        })
                      )}
                  </svg>
                </div>

                {/* Evidence column */}
                <div style={{ flex: 1, padding: '0 12px' }}>
                  <div style={{ height: headerH, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, color: '#00b894', paddingBottom: 6, borderBottom: '2px solid #00b894', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <i className="fas fa-search" /> Evidence
                  </div>
                  {parsed.evidence.length > 0 ? parsed.evidence.map((e, i) => {
                    const evVerdict = String(e.verdict || 'pending');
                    const vBg = evVerdict.includes('support') ? '#28a745' : evVerdict.includes('refut') ? '#dc3545' : 'var(--cha-bg-main)';
                    const vColor = evVerdict === 'pending' ? 'var(--cha-text-muted)' : 'white';
                    return (
                      <div key={i} style={{ height: cardH, border: '2px solid var(--cha-border)', borderLeft: '4px solid #00b894', borderRadius: 8, padding: '10px 12px', marginBottom: cardGap, background: 'var(--cha-bg-white)', fontSize: 11, overflow: 'hidden', boxSizing: 'border-box' }}>
                        <div style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700, color: '#00b894', marginBottom: 3 }}>{String(e.id || e.agent || `ER-${i + 1}`)}</div>
                        <div style={{ color: 'var(--cha-text-secondary)', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis' }}>{String(e.description || e.content || '').slice(0, 60)}</div>
                        <span style={{ display: 'inline-block', fontSize: 9, fontWeight: 700, marginTop: 2, padding: '1px 6px', borderRadius: 3, background: vBg, color: vColor }}>{evVerdict}</span>
                      </div>
                    );
                  }) : <div style={{ color: 'var(--cha-text-muted)', fontSize: 11, marginTop: 10 }}>No evidence yet</div>}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ═══ AGENT FLOW VIEW ═══ */}
      {activeView === 'flow' && (() => {
        const agentTurns = events.filter(e => e.event_type === 'agent_turn' || (e.event_type === 'phase_change' && e.agent_name));
        const agentNames = [...new Set(agentTurns.map(e => e.agent_name).filter(Boolean))];
        const phaseCounts: Record<string, number> = {};
        agentTurns.forEach(e => { if (e.phase) phaseCounts[e.phase] = (phaseCounts[e.phase] || 0) + 1; });

        const AGENT_ICONS: Record<string, string> = {
          orchestrator: 'fa-sitemap', triage: 'fa-filter', hypothesis_selector: 'fa-lightbulb',
          evidence_planner: 'fa-clipboard-list', telemetry_agent: 'fa-chart-line', outage_agent: 'fa-exclamation-triangle',
          support_agent: 'fa-headset', advisor_agent: 'fa-shield-alt', resource_agent: 'fa-server',
          reasoner: 'fa-brain', action_planner: 'fa-tasks', notification_agent: 'fa-bell',
        };

        let lastPhase = '';

        return (
          <div style={{ border: '1px solid var(--cha-border)', borderRadius: 'var(--cha-radius-md)', overflow: 'hidden' }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', background: 'var(--cha-bg-main)', borderBottom: '1px solid var(--cha-border)' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--cha-text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <i className="fas fa-route" /> Agent Execution Flow
              </span>
              <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--cha-text-muted)' }}>
                {['triage', 'hypothesizing', 'collecting', 'reasoning', 'acting', 'notifying'].map(p => (
                  <span key={p} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: PHASE_COLORS[p], display: 'inline-block' }} />
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </span>
                ))}
              </div>
            </div>
            {/* Flow */}
            <div style={{ padding: '32px 24px', overflowX: 'auto' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
                {agentTurns.map((evt, i) => {
                  const phaseColor = PHASE_COLORS[evt.phase] || '#17a2b8';
                  const agentKey = (evt.agent_name || '').toLowerCase();
                  const icon = AGENT_ICONS[agentKey] || 'fa-cog';
                  const displayName = evt.agent_name
                    ? evt.agent_name.replace(/_/g, ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
                    : evt.event_type.replace(/_/g, ' ');
                  const showSep = lastPhase !== '' && evt.phase !== lastPhase;
                  const sep = showSep ? lastPhase : null;
                  lastPhase = evt.phase;

                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                      {/* Phase separator */}
                      {sep && (
                        <div style={{ width: 2, minHeight: 80, background: 'var(--cha-border)', margin: '0 8px', borderRadius: 1, position: 'relative', flexShrink: 0 }}>
                          <span style={{ position: 'absolute', top: -16, left: '50%', transform: 'translateX(-50%)', fontSize: 8, fontWeight: 700, textTransform: 'uppercase', color: 'var(--cha-text-muted)', whiteSpace: 'nowrap', background: 'var(--cha-bg-white)', padding: '0 4px' }}>
                            {evt.phase.toUpperCase()}
                          </span>
                        </div>
                      )}
                      {/* Arrow before node (except first) */}
                      {i > 0 && !sep && (
                        <svg width="32" height="20" style={{ flexShrink: 0 }}>
                          <path d="M0,10 L24,10" stroke="var(--cha-border)" strokeWidth="2" fill="none" />
                          <polygon points="24,5 32,10 24,15" fill="var(--cha-text-muted)" />
                        </svg>
                      )}
                      {/* Agent node */}
                      <div style={{
                        minWidth: 140, maxWidth: 170, padding: '12px 14px', borderRadius: 10,
                        border: `2px solid ${phaseColor}`, background: 'var(--cha-bg-white)',
                        textAlign: 'center', position: 'relative', cursor: 'default', transition: '0.2s ease',
                      }}>
                        {/* Tick badge */}
                        <span style={{ position: 'absolute', top: -9, right: -6, fontSize: 8, fontWeight: 700, background: '#1e3c72', color: 'white', padding: '2px 6px', borderRadius: 10, zIndex: 2 }}>#{i + 3}</span>
                        {/* Icon */}
                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: phaseColor, color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '-24px auto 6px', fontSize: 14, border: '3px solid var(--cha-bg-white)' }}>
                          <i className={`fas ${icon}`} />
                        </div>
                        <div style={{ fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{displayName}</div>
                        <span style={{ display: 'inline-block', fontSize: 8, fontWeight: 600, textTransform: 'uppercase', marginTop: 3, padding: '2px 8px', borderRadius: 4, background: phaseColor, color: 'white', letterSpacing: 0.5 }}>{evt.phase}</span>
                        <div style={{ fontSize: 8, color: 'var(--cha-text-muted)', marginTop: 4, maxWidth: 140, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{evt.content.slice(0, 40)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            {/* Stats */}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 16px', borderTop: '1px solid var(--cha-border)', background: 'var(--cha-bg-main)', fontSize: 11, color: 'var(--cha-text-secondary)', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: 16 }}>
                <span><strong>{agentTurns.length}</strong> total turns</span>
                <span><strong>{agentNames.length}</strong> agents used</span>
                <span><strong>{Object.keys(phaseCounts).length}</strong> phase transitions</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {Object.entries(phaseCounts).map(([phase, count]) => (
                  <span key={phase} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: PHASE_COLORS[phase] || 'var(--cha-border)', display: 'inline-block' }} />
                    {count}
                  </span>
                ))}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Resolution panel */}
      {done && (() => {
        const report = parsed.report;
        const rootCause = String(report?.root_cause || sc.expected_root_cause);
        const confidence = String(report?.confidence || '');
        const factors = (report?.contributing_factors || []) as string[];
        const recActions = (report?.recommended_actions || parsed.actions) as Record<string, unknown>[];
        const timeline = (report?.timeline || []) as Record<string, unknown>[];
        const customer = String(report?.customer || 'Blackrock Production (East US)');
        const invId = String(report?.investigation_id || '');
        const status = String(report?.status || 'COMPLETE');

        return (
          <div className="cha-resolution">
            <h3><i className="fas fa-check-circle" /> Investigation Resolved</h3>

            <div className="rp-label">ROOT CAUSE</div>
            <div className="rp-value">{rootCause}</div>

            {confidence && (
              <>
                <div className="rp-label">CONFIDENCE</div>
                <div className="rp-value">{confidence}</div>
              </>
            )}

            {factors.length > 0 && (
              <>
                <div className="rp-label">CONTRIBUTING FACTORS</div>
                <div className="rp-value">
                  {factors.map((f, i) => <div key={i} style={{ marginBottom: 2 }}>↳ {f}</div>)}
                </div>
              </>
            )}

            <div className="rp-label">RESOLUTION SUMMARY</div>
            <div className="rp-value" style={{ fontSize: 12 }}>
              Customer: {customer}<br />
              {invId && <>Investigation ID: {invId}<br /></>}
              Status: {status}<br />
              {report?.timestamp ? <>Timestamp: {String(report.timestamp)}<br /></> : null}
              <br />
              Root Cause: {rootCause}
            </div>

            {recActions.length > 0 && (
              <>
                <div className="rp-label">ACTIONS TAKEN</div>
                <div className="rp-value">
                  {recActions.map((a, i) => (
                    <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginRight: 8, marginBottom: 4, fontSize: 12 }}>
                      {String(a.display_name || a.action || a.name || '')} ({String(a.tier || 'auto')}) <i className="fas fa-check" style={{ color: '#28a745', fontSize: 10 }} />
                    </span>
                  ))}
                </div>
              </>
            )}

            {timeline.length > 0 && (
              <>
                <div className="rp-label">TIMELINE</div>
                <div className="rp-value" style={{ fontSize: 12 }}>
                  {timeline.map((t, i) => (
                    <div key={i} style={{ marginBottom: 2 }}>
                      <strong>{String(t.timestamp || '')}</strong> — {String(t.event || '')}
                    </div>
                  ))}
                </div>
              </>
            )}

            <div style={{ display: 'flex', gap: 16, marginTop: 12, paddingTop: 12, borderTop: '1px solid #d4edda' }}>
              <div>
                <div className="rp-label">TOTAL AGENT TURNS</div>
                <div className="rp-value">{tickCount}</div>
              </div>
              <div>
                <div className="rp-label">PHASES COMPLETED</div>
                <div className="rp-value">{phaseIdx + 1} / {PHASES.length}</div>
              </div>
            </div>

            <div style={{ marginTop: 16 }}>
              <button className="cha-btn-primary" onClick={() => { setScenario(null); setEvents([]); setDone(false); setCurrentPhase(''); setTickCount(0); }}>
                <i className="fas fa-redo" /> Run Another Investigation
              </button>
            </div>
          </div>
        );
      })()}
    </>
  );
}
