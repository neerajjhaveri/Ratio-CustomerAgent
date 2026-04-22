import { useEffect, useState } from 'react';
import { listKnowledge, getKnowledgeContent, type KnowledgeFile } from '../../api/customerAgentClient';

const KNOWLEDGE_ICONS: Record<string, string> = {
  'confidence_scoring.md': 'fa-calculator',
  'customer_health_reasoning.md': 'fa-heart-pulse',
  'evidence_evaluation_matrix.md': 'fa-balance-scale',
  'sli_interpretation.md': 'fa-chart-line',
  'timing_correlation.md': 'fa-clock',
};

export default function ChaKnowledgePage() {
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [viewer, setViewer] = useState<{ title: string; content: string } | null>(null);

  useEffect(() => { listKnowledge().then(setFiles).catch(() => {}); }, []);

  const openFile = async (name: string) => {
    try {
      const data = await getKnowledgeContent(name);
      setViewer(data);
    } catch { /* ignore */ }
  };

  return (
    <>
      <div className="cha-knowledge-grid">
        {files.map(f => {
          const icon = KNOWLEDGE_ICONS[f.name] || 'fa-file-alt';
          return (
            <div key={f.name} className="cha-knowledge-card" onClick={() => openFile(f.name)}>
              <div style={{ fontSize: 24, color: 'var(--cha-primary)', marginBottom: 8 }}>
                <i className={`fas ${icon}`} />
              </div>
              <h4>{f.title}</h4>
              <p>{f.preview}</p>
              <div className="meta">{f.name} · {f.size}</div>
            </div>
          );
        })}
      </div>

      {viewer && (
        <div className="cha-knowledge-viewer">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>{viewer.title}</h3>
            <button className="cha-btn-run" style={{ background: 'var(--cha-danger)' }} onClick={() => setViewer(null)}>
              <i className="fas fa-times" /> Close
            </button>
          </div>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6 }}>{viewer.content}</pre>
        </div>
      )}
    </>
  );
}
