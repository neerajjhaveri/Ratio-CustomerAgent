/**
 * ResultsSummary — header strip showing evaluation counts by status (good/warning/bad).
 */
import Badge from 'react-bootstrap/Badge';
import type { EvaluateScenarioResponse } from '../../types/fuse';

interface ResultsSummaryProps {
  result: EvaluateScenarioResponse;
}

export default function ResultsSummary({ result }: ResultsSummaryProps) {
  const goodCount = result.metrics.filter((m) => m.status === 'good').length;
  const warningCount = result.metrics.filter((m) => m.status === 'warning').length;
  const badCount = result.metrics.filter((m) => m.status === 'bad').length;

  return (
    <div className="d-flex align-items-center justify-content-between mb-3">
      <div>
        <h4 className="fw-bold mb-0" style={{ color: '#1e3a5f' }}>
          Evaluation Results
        </h4>
        <small className="text-muted">
          {result.scenario_name} — {result.case_count} case{result.case_count !== 1 ? 's' : ''} evaluated
        </small>
      </div>
      <div className="d-flex gap-2">
        {goodCount > 0 && (
          <Badge bg="success" style={{ fontSize: '0.8rem' }}>
            <i className="bi bi-check-circle me-1" />{goodCount} Good
          </Badge>
        )}
        {warningCount > 0 && (
          <Badge bg="warning" text="dark" style={{ fontSize: '0.8rem' }}>
            <i className="bi bi-exclamation-triangle me-1" />{warningCount} Warning
          </Badge>
        )}
        {badCount > 0 && (
          <Badge bg="danger" style={{ fontSize: '0.8rem' }}>
            <i className="bi bi-x-circle me-1" />{badCount} Bad
          </Badge>
        )}
      </div>
    </div>
  );
}
