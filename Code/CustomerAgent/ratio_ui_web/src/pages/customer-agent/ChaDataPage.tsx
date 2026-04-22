import { useEffect, useState, useRef } from 'react';
import { listDatafiles, getDatafile, type DataFileInfo } from '../../api/customerAgentClient';

export default function ChaDataPage() {
  const [files, setFiles] = useState<DataFileInfo[]>([]);
  const [preview, setPreview] = useState<{ name: string; path: string; records: Record<string, unknown>[] } | null>(null);
  const previewRef = useRef<HTMLDivElement>(null);

  useEffect(() => { listDatafiles().then(setFiles).catch(() => {}); }, []);

  const openFile = async (file: DataFileInfo) => {
    try {
      const data = await getDatafile(file.path);
      setPreview({ ...data, path: file.path });
      setTimeout(() => previewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    } catch { /* ignore */ }
  };

  // Group files by directory
  const groups: Record<string, DataFileInfo[]> = {};
  files.forEach(f => {
    const dir = f.path.split('/')[0] || 'other';
    if (!groups[dir]) groups[dir] = [];
    groups[dir].push(f);
  });

  const formatDir = (d: string) => d.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <>
      {Object.entries(groups).map(([dir, dirFiles]) => (
        <div key={dir} style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, color: 'var(--cha-text-secondary)', padding: '16px 0 8px', borderBottom: '1px solid var(--cha-border)', marginBottom: 12 }}>
            <i className="fas fa-folder" style={{ marginRight: 6, color: 'var(--cha-primary)' }} />
            {formatDir(dir)} ({dirFiles.length})
          </div>
          <div className="cha-datafile-grid">
            {dirFiles.map(f => (
              <div key={f.path} className="cha-datafile-card" onClick={() => openFile(f)}>
                <h5><i className="fas fa-file-alt" style={{ marginRight: 6, color: 'var(--cha-primary)' }} />{f.name}</h5>
                <div className="meta" style={{ marginBottom: 8 }}>
                  {f.record_count} records · {f.columns?.length ?? 0} columns · {f.size}
                </div>
                {f.columns && f.columns.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    {f.columns.slice(0, 8).map(c => (
                      <span key={c} className="cha-param-tag">{c}</span>
                    ))}
                    {f.columns.length > 8 && (
                      <span className="cha-param-tag" style={{ background: 'var(--cha-bg-main)', color: 'var(--cha-text-muted)' }}>+{f.columns.length - 8} more</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {preview && (
        <div className="cha-data-preview" ref={previewRef} style={{ overflow: 'hidden' }}>
          <div className="cha-data-preview-header" style={{ background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)', color: 'white' }}>
            <h4 style={{ margin: 0, fontSize: 14, color: 'white' }}>
              <i className="fas fa-table" style={{ marginRight: 8 }} />
              {preview.name} — Preview (first 20 rows)
            </h4>
            <button style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: 'white', padding: '4px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }} onClick={() => setPreview(null)}>
              <i className="fas fa-times" /> Close
            </button>
          </div>
          {preview.records.length > 0 ? (
            <div style={{ maxHeight: 400, overflowY: 'auto', overflowX: 'auto' }}>
              <table className="cha-table">
                <thead>
                  <tr>{Object.keys(preview.records[0]).map(k => <th key={k} style={{ background: '#2a3f6f', color: 'white', position: 'sticky', top: 0, zIndex: 1 }}>{k}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.records.slice(0, 20).map((rec, i) => (
                    <tr key={i}>
                      {Object.entries(rec).map(([k, v], j) => (
                        <td key={j} className={k.endsWith('_id') || k === 'id' ? 'cha-id-cell' : ''}>
                          {typeof v === 'object' && v !== null
                            ? <pre style={{ margin: 0, fontSize: 10, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>{JSON.stringify(v, null, 1)}</pre>
                            : String(v ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 20, color: 'var(--cha-text-muted)' }}>No records</div>
          )}
        </div>
      )}
    </>
  );
}
