/**
 * RecommendationsPanel — displays triggered improvement actions grouped by priority.
 */
import Alert from 'react-bootstrap/Alert';
import Badge from 'react-bootstrap/Badge';
import Card from 'react-bootstrap/Card';
import type { Recommendation } from '../../types/fuse';

interface RecommendationsPanelProps {
  recommendations: Recommendation[];
}

export default function RecommendationsPanel({ recommendations }: RecommendationsPanelProps) {
  if (recommendations.length === 0) return null;

  return (
    <Card className="mb-4 border-0 shadow-sm">
      <Card.Header className="bg-white border-bottom">
        <div className="d-flex align-items-center">
          <span
            className="d-inline-flex align-items-center justify-content-center rounded-circle me-2"
            style={{ width: 24, height: 24, background: '#16a34a', color: '#fff', fontSize: '0.75rem', fontWeight: 700 }}
          >
            4
          </span>
          <strong>Improvement Actions</strong>
          <Badge bg="secondary" className="ms-2">{recommendations.length}</Badge>
          <small className="text-muted ms-2">— What to fix, based on which metrics breached thresholds</small>
        </div>
      </Card.Header>
      <Card.Body>
        {recommendations.map((rec, index) => (
          <Alert
            key={`${rec.metric_id}-${index}`}
            variant={rec.priority === 'high' ? 'danger' : rec.priority === 'medium' ? 'warning' : 'info'}
            className="mb-2"
          >
            <div className="d-flex align-items-start">
              <Badge
                bg={rec.priority === 'high' ? 'danger' : rec.priority === 'medium' ? 'warning' : 'info'}
                className="me-2 mt-1"
                style={{ fontSize: '0.7rem' }}
              >
                {rec.priority.toUpperCase()}
              </Badge>
              <div>
                <strong style={{ fontSize: '0.85rem' }}>{rec.metric_id}</strong>
                <span className="text-muted mx-1">—</span>
                <span style={{ fontSize: '0.85rem' }}>{rec.message}</span>
                <ul className="mb-0 mt-1" style={{ fontSize: '0.82rem' }}>
                  {rec.suggested_actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </div>
            </div>
          </Alert>
        ))}
      </Card.Body>
    </Card>
  );
}
