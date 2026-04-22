import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listScenarios, type Scenario } from '../../api/customerAgentClient';

export default function ChaScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [filter, setFilter] = useState('all');
  const navigate = useNavigate();

  useEffect(() => { listScenarios().then(setScenarios).catch(() => {}); }, []);

  const filtered = filter === 'all'
    ? scenarios
    : scenarios.filter(s => {
        if (filter === 'single') return s.category === 'singular';
        if (filter === 'compound') return s.category === 'composite';
        if (filter === 'cascading') return s.category === 'edge_case';
        return true;
      });

  return (
    <>
      <div className="cha-filters">
        {['all','single','compound','cascading'].map(f => (
          <button key={f} className={`cha-filter-btn${filter === f ? ' active' : ''}`} onClick={() => setFilter(f)}>
            {f === 'all' ? 'All' : f === 'single' ? 'Single Signal' : f === 'compound' ? 'Compound' : 'Cascading'}
          </button>
        ))}
      </div>
      <div className="cha-card-grid-2">
        {filtered.map(s => (
          <div key={s.id} className="cha-scenario-card">
            <div className="cha-sc-header">
              <span className="cha-sc-id">{s.id}</span>
              <span className="cha-sc-expected">{s.expected_outcome.slice(0, 120).toUpperCase()}</span>
            </div>
            <div className="cha-sc-name">{s.name}</div>
            <div className="cha-sc-desc">{s.description}</div>
            <div className="cha-sc-meta">
              <span className="cha-sc-tag">{s.category}</span>
              <span className="cha-sc-tag">{s.signal_count} signal{s.signal_count !== 1 ? 's' : ''}</span>
            </div>
            <button className="cha-btn-run" onClick={() => {
              sessionStorage.setItem('cha-run-scenario', s.id);
              navigate('/customer-agent/active');
            }}>
              <i className="fas fa-play" /> Run Scenario
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
