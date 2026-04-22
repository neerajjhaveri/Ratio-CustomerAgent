import { useEffect, useState } from 'react';
import { listAgents, type AgentInfo } from '../../api/customerAgentClient';

export default function ChaAgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);

  useEffect(() => { listAgents().then(setAgents).catch(() => {}); }, []);

  return (
    <div className="cha-agent-grid">
      {agents.map(a => (
        <div key={a.name} className="cha-agent-card">
          <div className="cha-agent-name">{a.display_name}</div>
          <div className="cha-agent-role">{a.role.replace(/_/g, ' ')}</div>
          <div className="cha-agent-desc">{a.description}</div>
          <div className="cha-agent-model">{a.model}</div>
          {a.technology_tags && a.technology_tags.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {a.technology_tags.map(t => <span key={t} className="cha-agent-tag">{t}</span>)}
            </div>
          )}
          {a.tool_names.length > 0 && (
            <div className="cha-agent-tools">
              Tools: {a.tool_names.join(', ')}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
