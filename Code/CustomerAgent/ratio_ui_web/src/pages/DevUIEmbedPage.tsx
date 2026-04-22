import Badge from 'react-bootstrap/Badge';
import Alert from 'react-bootstrap/Alert';
import { useState } from 'react';

const DEVUI_URL = 'http://127.0.0.1:8090';

export default function DevUIEmbedPage() {
  const [loadError, setLoadError] = useState(false);

  return (
    <div className="d-flex flex-column" style={{ height: '100vh' }}>
      {/* Header bar */}
      <div
        className="d-flex align-items-center justify-content-between px-4 py-2"
        style={{ borderBottom: '1px solid #dee2e6', background: '#fff', flexShrink: 0 }}
      >
        <div className="d-flex align-items-center gap-2">
          <h5 className="mb-0">
            <i className="bi bi-terminal me-2" />
            Agent DevUI Studio
          </h5>
          <Badge bg="info">Embedded</Badge>
        </div>
        <div className="d-flex align-items-center gap-2">
          <a
            href={DEVUI_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-outline-secondary btn-sm"
          >
            <i className="bi bi-box-arrow-up-right me-1" />
            Open Full DevUI
          </a>
          <Badge bg="secondary">Port 8090</Badge>
        </div>
      </div>

      {/* Error message if DevUI isn't running */}
      {loadError && (
        <Alert variant="warning" className="m-3 mb-0" dismissible onClose={() => setLoadError(false)}>
          <Alert.Heading>DevUI not available</Alert.Heading>
          <p className="mb-1">
            The Agent Framework DevUI server is not running on port 8090.
          </p>
          <p className="mb-0">
            Start it with: <code>cd src/services/ratio_agents && python devui_serve.py</code>
          </p>
        </Alert>
      )}

      {/* Embedded DevUI iframe */}
      <iframe
        src={DEVUI_URL}
        title="Agent Framework DevUI"
        onError={() => setLoadError(true)}
        style={{
          flex: 1,
          width: '100%',
          border: 'none',
          display: loadError ? 'none' : 'block',
        }}
        allow="clipboard-write"
      />
    </div>
  );
}
