/**
 * DiagnosticsPanel — per-case failure mode and signal detail in a collapsible accordion.
 */
import Accordion from 'react-bootstrap/Accordion';
import Badge from 'react-bootstrap/Badge';
import Card from 'react-bootstrap/Card';
import type { CaseDecisionResult } from '../../types/fuse';

interface DiagnosticsPanelProps {
  diagnostics: CaseDecisionResult[];
}

export default function DiagnosticsPanel({ diagnostics }: DiagnosticsPanelProps) {
  if (!diagnostics || diagnostics.length === 0) return null;

  return (
    <Accordion className="mt-3">
      <Accordion.Item eventKey="diagnostics">
        <Accordion.Header>
          <i className="bi bi-search me-2" />
          Case-Level Diagnostics ({diagnostics.length} cases)
        </Accordion.Header>
        <Accordion.Body>
          {diagnostics.map((diag) => {
            const triggeredModes = diag.failure_modes.filter((fm) => fm.triggered);
            return (
              <Card key={diag.case_id} className="mb-2">
                <Card.Body className="py-2 px-3">
                  <div className="d-flex align-items-center justify-content-between mb-1">
                    <strong style={{ fontSize: '0.85rem' }}>
                      <i className="bi bi-file-earmark-text me-1" />
                      {diag.case_id}
                    </strong>
                    {triggeredModes.length > 0 ? (
                      <Badge bg="danger" pill>
                        {triggeredModes.length} failure{triggeredModes.length > 1 ? 's' : ''}
                      </Badge>
                    ) : (
                      <Badge bg="success" pill>No failures</Badge>
                    )}
                  </div>
                  {triggeredModes.length > 0 && (
                    <div className="d-flex flex-wrap gap-1 mb-1">
                      {triggeredModes.map((fm) => (
                        <Badge
                          key={fm.failure_mode_id}
                          bg="outline-danger"
                          text="danger"
                          style={{ border: '1px solid #dc2626', background: '#fef2f2', fontSize: '0.75rem' }}
                        >
                          <i className="bi bi-exclamation-circle me-1" />
                          {fm.failure_mode_id.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {diag.errors.length > 0 && (
                    <div className="mt-1">
                      {diag.errors.map((err, i) => (
                        <small key={i} className="d-block text-danger" style={{ fontSize: '0.75rem' }}>
                          ⚠ {err}
                        </small>
                      ))}
                    </div>
                  )}
                </Card.Body>
              </Card>
            );
          })}
        </Accordion.Body>
      </Accordion.Item>
    </Accordion>
  );
}
