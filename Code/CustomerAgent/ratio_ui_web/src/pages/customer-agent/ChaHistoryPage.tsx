import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listInvestigations, listScenarios, type PastInvestigation, type Scenario } from '../../api/customerAgentClient';

// Map scenario IDs to names
const SCENARIO_NAMES: Record<string, string> = {};

export default function ChaHistoryPage() {
  const [investigations, setInvestigations] = useState<PastInvestigation[]>([]);
  const [scenarios, setScenarios] = useState<Record<string, Scenario>>({});
  const navigate = useNavigate();

  useEffect(() => {
    listInvestigations().then(setInvestigations).catch(() => {});
    listScenarios().then(list => {
      const map: Record<string, Scenario> = {};
      list.forEach(s => { map[s.id] = s; });
      setScenarios(map);
    }).catch(() => {});
  }, []);

  if (investigations.length === 0) {
    return (
      <div className="cha-empty-state">
        <i className="fas fa-history" />
        <h3>Investigation History</h3>
        <p>Run a simulation scenario to populate history.</p>
      </div>
    );
  }

  const formatDate = (d: string) => {
    if (!d) return '';
    const dt = new Date(d);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[dt.getMonth()]} ${dt.getDate()}, ${dt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  };

  return (
    <div style={{ paddingTop: 16 }}>
      {investigations.map(inv => {
        const sc = scenarios[inv.scenario_id];
        const name = sc?.name || inv.scenario_id;
        const isComplete = inv.phase === 'complete';

        return (
          <div key={inv.id} className="cha-history-item" style={{ borderLeft: `4px solid ${isComplete ? 'var(--cha-success)' : 'var(--cha-warning)'}` }}>
            {/* Left: status icon + info */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1 }}>
              <div style={{
                width: 40, height: 40, borderRadius: '50%',
                background: isComplete ? 'var(--cha-success-light)' : 'var(--cha-warning-light)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <i className={`fas ${isComplete ? 'fa-check' : 'fa-spinner'}`}
                  style={{ color: isComplete ? 'var(--cha-success)' : 'var(--cha-warning)', fontSize: 16 }} />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{name}</div>
                <div style={{ fontSize: 12, color: 'var(--cha-text-muted)' }}>{inv.scenario_id}</div>
                <div style={{ fontSize: 11, color: 'var(--cha-text-muted)', marginTop: 4 }}>
                  Started: {formatDate(inv.started_at)}
                  {inv.completed_at && <> · Completed: {formatDate(inv.completed_at)}</>}
                </div>
              </div>
            </div>

            {/* Right: stats + badge + re-run */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--cha-text-muted)' }}>
                <div><i className="fas fa-play" style={{ marginRight: 4 }} />{formatDate(inv.started_at)}</div>
                <div><i className="fas fa-hashtag" style={{ marginRight: 4 }} />{inv.hypothesis_count} hypotheses · {inv.evidence_count} evidence</div>
              </div>
              <span className="cha-badge" style={{
                background: isComplete ? 'var(--cha-success-light)' : 'var(--cha-warning-light)',
                color: isComplete ? 'var(--cha-success)' : 'var(--cha-warning)',
                border: `1px solid ${isComplete ? '#b7e1c7' : '#f5d89a'}`,
              }}>
                {inv.phase}
              </span>
              <button className="cha-btn-run" onClick={() => {
                sessionStorage.setItem('cha-run-scenario', inv.scenario_id);
                navigate('/customer-agent/active');
              }}>
                <i className="fas fa-redo" /> Re-run
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
