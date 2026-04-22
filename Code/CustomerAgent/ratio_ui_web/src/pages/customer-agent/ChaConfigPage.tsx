import { useEffect, useState, useCallback } from 'react';
import { getConfigTab, listAgents, listKnowledge, getKnowledgeContent, type AgentInfo, type ConfigItem, type KnowledgeFile } from '../../api/customerAgentClient';

const TABS = [
  { key: 'agents', icon: 'fa-robot', label: 'Agents' },
  { key: 'symptoms', icon: 'fa-stethoscope', label: 'Symptoms' },
  { key: 'hypotheses', icon: 'fa-lightbulb', label: 'Hypotheses' },
  { key: 'evidence', icon: 'fa-search', label: 'Evidence' },
  { key: 'actions', icon: 'fa-bolt', label: 'Actions' },
  { key: 'knowledge', icon: 'fa-book', label: 'Knowledge' },
  { key: 'customers', icon: 'fa-building', label: 'Customers' },
  { key: 'channels', icon: 'fa-paper-plane', label: 'Channels' },
];

const AGENT_COLORS = ['#7c3aed','#4f6bed','#0984e3','#00b894','#e17055','#d63031','#e84393','#fdcb6e','#00cec9','#6c5ce7','#636e72','#fab1a0'];

const AGENT_ICONS: Record<string, string> = {
  action_planner: 'fa-tasks',
  advisor_agent: 'fa-shield-alt',
  evidence_planner: 'fa-clipboard-list',
  hypothesis_selector: 'fa-lightbulb',
  notification_agent: 'fa-bell',
  orchestrator: 'fa-sitemap',
  outage_agent: 'fa-exclamation-triangle',
  reasoner: 'fa-brain',
  resource_agent: 'fa-server',
  support_agent: 'fa-headset',
  telemetry_agent: 'fa-chart-line',
  triage: 'fa-filter',
};

const KNOWLEDGE_ICONS: Record<string, string> = {
  'confidence_scoring.md': 'fa-calculator',
  'customer_health_reasoning.md': 'fa-heart-pulse',
  'evidence_evaluation_matrix.md': 'fa-balance-scale',
  'sli_interpretation.md': 'fa-chart-line',
  'timing_correlation.md': 'fa-clock',
};

export default function ChaConfigPage() {
  const [activeTab, setActiveTab] = useState('agents');
  const [items, setItems] = useState<ConfigItem[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeFile[]>([]);
  const [knowledgeViewer, setKnowledgeViewer] = useState<{ title: string; content: string } | null>(null);
  const [rawData, setRawData] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);

  const loadTab = useCallback(async (tab: string) => {
    setLoading(true);
    setKnowledgeViewer(null);
    try {
      if (tab === 'agents') {
        const a = await listAgents();
        setAgents(a);
        setItems([]);
        setRawData({});
      } else if (tab === 'knowledge') {
        const k = await listKnowledge();
        setKnowledge(k);
        setItems([]);
        setRawData({});
      } else if (tab === 'customers' || tab === 'channels') {
        // These return non-standard shapes — store raw
        const res = await fetch(`/customer-agent-api/api/config/${tab}`);
        const data = await res.json();
        setRawData(data);
        setItems([]);
      } else {
        const data = await getConfigTab(tab);
        setItems(data);
        setRawData({});
      }
    } catch { setItems([]); setRawData({}); }
    setLoading(false);
  }, []);

  useEffect(() => { loadTab(activeTab); }, [activeTab, loadTab]);

  const renderAgentsTab = () => (
    <div className="cha-cfg-agent-grid">
      {agents.map((a, i) => (
        <div key={a.name} className="cha-cfg-agent-card">
          <div className="cha-cfg-agent-header">
            <div className="cha-cfg-agent-avatar" style={{ background: AGENT_COLORS[i % AGENT_COLORS.length] }}>
              <i className={`fas ${AGENT_ICONS[a.name] || 'fa-robot'}`} />
            </div>
            <div className="cha-cfg-agent-title">
              <div className="name">{a.display_name}</div>
              <div className="role">{a.role.replace(/_/g, ' ')}</div>
            </div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--cha-text-secondary)', marginBottom: 8 }}>{a.description}</div>
          {a.objective && (
            <>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginBottom: 4 }}>OBJECTIVE</div>
              <div style={{ fontSize: 12, color: 'var(--cha-text-secondary)', background: 'var(--cha-bg-main)', padding: '8px 12px', borderRadius: 6, marginBottom: 8, lineHeight: 1.5 }}>
                {a.objective}
              </div>
            </>
          )}
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginBottom: 4 }}>MODEL & TAGS</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
            <span className="cha-agent-model">{a.model} · temp {a.temperature ?? 0}</span>
            {a.technology_tags?.map(t => <span key={t} className="cha-agent-tag">{t}</span>)}
          </div>
          {a.tool_names.length > 0 && (
            <>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginTop: 8, marginBottom: 4 }}>TOOLS ({a.tool_names.length})</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{a.tool_names.map(t => <span key={t} className="cha-param-tag">{t}</span>)}</div>
            </>
          )}
        </div>
      ))}
    </div>
  );

  const openKnowledgeFile = async (name: string) => {
    try {
      const data = await getKnowledgeContent(name);
      setKnowledgeViewer(data);
    } catch { /* ignore */ }
  };

  const renderKnowledgeTab = () => (
    <>
      <div className="cha-knowledge-grid">
        {knowledge.map(k => {
          const icon = KNOWLEDGE_ICONS[k.name] || 'fa-file-alt';
          return (
            <div key={k.name} className="cha-knowledge-card" onClick={() => openKnowledgeFile(k.name)}>
              <div style={{ fontSize: 24, color: 'var(--cha-primary)', marginBottom: 8 }}>
                <i className={`fas ${icon}`} />
              </div>
              <h4>{k.title}</h4>
              <p>{k.preview}</p>
              <div className="meta">{k.name} · {k.size}</div>
            </div>
          );
        })}
      </div>
      {knowledgeViewer && (
        <div className="cha-knowledge-viewer" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 20px', background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)', color: 'white', borderRadius: '10px 10px 0 0' }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{knowledgeViewer.title}</h3>
            <button style={{ background: 'none', border: 'none', color: 'white', fontSize: 18, cursor: 'pointer', padding: '4px 8px' }} onClick={() => setKnowledgeViewer(null)}>
              <i className="fas fa-times" />
            </button>
          </div>
          <div style={{ padding: '16px 20px', maxHeight: 400, overflowY: 'auto' }}>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{knowledgeViewer.content}</pre>
          </div>
        </div>
      )}
    </>
  );

  const TAB_COLUMNS: Record<string, { key: string; label: string }[]> = {
    symptoms: [
      { key: 'id', label: 'ID' },
      { key: 'name', label: 'Name' },
      { key: 'category', label: 'Category' },
      { key: 'template', label: 'Template' },
      { key: 'extracted_when', label: 'Extracted When' },
      { key: 'filters', label: 'Filters' },
    ],
    hypotheses: [
      { key: 'id', label: 'ID' },
      { key: 'name', label: 'Name' },
      { key: 'category', label: 'Category' },
      { key: 'statement', label: 'Statement' },
      { key: 'applicable_symptoms', label: 'Applicable Symptoms' },
      { key: 'evidence_needed', label: 'Evidence Needed' },
    ],
    evidence: [
      { key: 'id', label: 'ID' },
      { key: 'description', label: 'Description' },
      { key: 'technology_tag', label: 'Tech Tag' },
      { key: 'tool_name', label: 'Tool' },
      { key: 'parameters', label: 'Parameters' },
    ],
    actions: [
      { key: 'id', label: 'ID' },
      { key: 'description', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'tier', label: 'Tier' },
      { key: 'applicable_hypotheses', label: 'Hypotheses' },
      { key: 'tool', label: 'Tool' },
    ],
  };

  const renderTable = () => {
    if (items.length === 0) return <div className="cha-empty-state"><i className="fas fa-inbox" /><h3>No data</h3></div>;
    const allKeys = Object.keys(items[0]).filter(k => k !== '__typename');
    const defined = TAB_COLUMNS[activeTab];

    // Use defined columns with custom labels, or fall back to API keys
    const columns: { key: string; label: string }[] = defined
      ? [
          ...defined.filter(c => allKeys.includes(c.key)),
          ...allKeys.filter(k => !defined.find(c => c.key === k)).map(k => ({ key: k, label: k.replace(/_/g, ' ') })),
        ]
      : allKeys.map(k => ({ key: k, label: k.replace(/_/g, ' ') }));

    return (
      <table className="cha-table">
        <thead>
          <tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i}>
              {columns.map(c => {
                const val = item[c.key];
                const isId = c.key === 'id' || c.key.endsWith('_id');
                const isArray = Array.isArray(val);
                const isCategory = c.key === 'category';
                const isTag = c.key === 'technology_tag' || c.key === 'tool_name' || c.key === 'tool';
                return (
                  <td key={c.key} className={isId ? 'cha-id-cell' : ''}>
                    {isCategory ? (
                      <span className="cha-category-badge" style={{ background: 'var(--cha-primary-light)', color: 'var(--cha-primary)' }}>{String(val)}</span>
                    ) : isTag && val ? (
                      <span className="cha-agent-tag">{String(val)}</span>
                    ) : isArray ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>{(val as string[]).map((v, j) => <span key={j} className="cha-param-tag">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>)}</div>
                    ) : typeof val === 'object' && val !== null ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>{Object.entries(val as Record<string, unknown>).map(([ek, ev]) => <span key={ek} className="cha-param-tag">{ek}: {String(ev)}</span>)}</div>
                    ) : (
                      String(val ?? '')
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  const renderCustomersTab = () => {
    const customer = rawData.customer as Record<string, unknown> | undefined;
    const subs = (rawData.subscription_ids || rawData.subscriptions || []) as string[];
    const rgPatterns = (rawData.resource_group_patterns || []) as string[];
    const resources = (rawData.resources || []) as Record<string, unknown>[];

    if (!customer) return <div className="cha-empty-state"><i className="fas fa-building" /><h3>No customer data</h3></div>;

    return (
      <div style={{ display: 'flex', gap: 24, paddingTop: 16 }}>
        <div className="cha-agent-card" style={{ minWidth: 260 }}>
          <div className="cha-agent-name">{customer.name as string}</div>
          <div style={{ fontSize: 12, color: 'var(--cha-primary)', marginBottom: 12 }}>{customer.customer_id as string}</div>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginBottom: 4 }}>SUBSCRIPTIONS</div>
          {subs.length > 0 ? subs.map((s, i) => <div key={i} style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--cha-text-secondary)', marginBottom: 2 }}>{s}</div>) : <div style={{ fontSize: 11, color: 'var(--cha-text-muted)' }}>—</div>}
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginTop: 12, marginBottom: 4 }}>RESOURCE GROUP PATTERNS</div>
          {rgPatterns.length > 0 ? rgPatterns.map((p, i) => <div key={i} style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--cha-text-secondary)', marginBottom: 2 }}>{p}</div>) : <div style={{ fontSize: 11, color: 'var(--cha-text-muted)' }}>—</div>}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginBottom: 8 }}>REGISTERED RESOURCES ({resources.length})</div>
          {resources.length > 0 ? (
            <table className="cha-table">
              <thead><tr><th>Resource ID</th><th>Service</th><th>Region</th><th>Resource Group</th></tr></thead>
              <tbody>
                {resources.map((r, i) => (
                  <tr key={i}>
                    <td className="cha-id-cell">{String(r.resource_id || '')}</td>
                    <td>{String(r.type || r.service || '')}</td>
                    <td>{String(r.region || '')}</td>
                    <td>{String(r.resource_group || '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div style={{ color: 'var(--cha-text-muted)', fontSize: 12 }}>No resources registered</div>}
        </div>
      </div>
    );
  };

  const CHANNEL_ICONS: Record<string, { icon: string; color: string }> = {
    'teams_webhook': { icon: 'fa-comments', color: '#6264A7' },
    'smtp': { icon: 'fa-envelope', color: '#dc3545' },
    'icm_api': { icon: 'fa-ticket-alt', color: '#e67e22' },
    'webhook': { icon: 'fa-plug', color: '#28a745' },
  };

  const renderChannelsTab = () => {
    const channels = (rawData.channels || []) as Record<string, unknown>[];
    const contacts = (rawData.contacts || []) as Record<string, unknown>[];

    return (
      <div style={{ paddingTop: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginBottom: 12 }}>NOTIFICATION CHANNELS ({channels.length})</div>
        <div className="cha-card-grid-2" style={{ marginBottom: 24 }}>
          {channels.map((ch, i) => {
            const ci = CHANNEL_ICONS[ch.type as string] || { icon: 'fa-bell', color: 'var(--cha-primary)' };
            return (
              <div key={i} className="cha-agent-card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 16 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: ci.color, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 16, flexShrink: 0 }}>
                  <i className={`fas ${ci.icon}`} />
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{ch.name as string}</div>
                  <div style={{ fontSize: 11, color: 'var(--cha-text-muted)' }}>{ch.type as string}</div>
                  <span className="cha-param-tag">{ch.config_key as string}</span>
                </div>
              </div>
            );
          })}
        </div>

        {contacts.length > 0 && (
          <>
            <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', color: 'var(--cha-text-muted)', marginBottom: 12 }}>CUSTOMER CONTACTS ({contacts.length})</div>
            <table className="cha-table">
              <thead><tr><th>Customer</th><th>TAM</th><th>TAM Email</th><th>Account Team</th></tr></thead>
              <tbody>
                {contacts.map((c, i) => (
                  <tr key={i}>
                    <td><strong>{c.customer as string}</strong><br /><span className="cha-id-cell">{c.customer_id as string}</span></td>
                    <td>{c.tam as string}</td>
                    <td><code style={{ fontSize: 11 }}>{c.tam_email as string}</code></td>
                    <td>{(c.account_team as string) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    );
  };

  const renderActionsTab = () => {
    if (items.length === 0) return <div className="cha-empty-state"><i className="fas fa-bolt" /><h3>No actions</h3></div>;
    return (
      <table className="cha-table">
        <thead>
          <tr><th>ID</th><th>Name</th><th>Type</th><th>Tier</th><th>Hypotheses</th><th>Tool</th></tr>
        </thead>
        <tbody>
          {items.map((a, i) => {
            const tier = String(a.tier || '');
            const isGated = tier === 'gated';
            const hyps = (a.applicable_hypotheses || []) as string[];
            return (
              <tr key={i}>
                <td className="cha-id-cell">{String(a.id || '')}</td>
                <td style={{ fontSize: 12, color: 'var(--cha-text-secondary)' }}>{String(a.description || a.name || '')}</td>
                <td></td>
                <td>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: isGated ? '#e67e22' : '#28a745' }}>
                    {isGated ? '🔒' : '⚡'} {tier}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    {hyps.map((h, j) => <span key={j} className="cha-param-tag">{h}</span>)}
                  </div>
                </td>
                <td></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  };

  return (
    <>
      <div className="cha-config-tabs">
        {TABS.map(t => (
          <button key={t.key} className={`cha-config-tab${activeTab === t.key ? ' active' : ''}`} onClick={() => setActiveTab(t.key)}>
            <i className={`fas ${t.icon}`} /> {t.label}
          </button>
        ))}
      </div>
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--cha-text-muted)' }}><i className="fas fa-spinner fa-spin" /> Loading…</div>
      ) : activeTab === 'agents' ? renderAgentsTab()
        : activeTab === 'knowledge' ? renderKnowledgeTab()
        : activeTab === 'customers' ? renderCustomersTab()
        : activeTab === 'channels' ? renderChannelsTab()
        : activeTab === 'actions' ? renderActionsTab()
        : renderTable()}
    </>
  );
}
