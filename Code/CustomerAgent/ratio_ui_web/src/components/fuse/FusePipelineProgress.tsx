/**
 * FusePipelineProgress — a visual pipeline tracker inspired by mission-control
 * progress UIs.  Shows each Fuse bucket as a status card with colour-coded
 * state, description of what filled the bucket, and a connecting progress bar.
 *
 * States: pending → in-progress → complete  (driven by the parent page).
 */
import Badge from 'react-bootstrap/Badge';
import Card from 'react-bootstrap/Card';

/* -------------------------------------------------------------------------- */
/*  Pipeline step definitions                                                 */
/* -------------------------------------------------------------------------- */

export interface PipelineStepStatus {
  state: 'pending' | 'in-progress' | 'complete';
  detail?: string;
  filledBy?: string;
}

interface StepDef {
  key: string;
  icon: string;
  title: string;
  color: string;
  desc: string;
  filledBy: string;
}

const STEPS: StepDef[] = [
  {
    key: 'business_goal',
    icon: 'bi-bullseye',
    title: 'Business Goal',
    color: '#2563eb',
    desc: 'What outcome matters?',
    filledBy: 'Scenario YAML (name + description)',
  },
  {
    key: 'agent_decision',
    icon: 'bi-signpost-split',
    title: 'Agent Decision',
    color: '#7c3aed',
    desc: 'What decisions does the agent make?',
    filledBy: 'Scenario YAML (derived signals)',
  },
  {
    key: 'failure_mode',
    icon: 'bi-exclamation-triangle',
    title: 'Failure Mode',
    color: '#dc2626',
    desc: 'What conditions indicate a bad decision?',
    filledBy: 'Fuse engine (YAML conditions evaluated per case)',
  },
  {
    key: 'signals',
    icon: 'bi-broadcast',
    title: 'Observable Signals',
    color: '#ea580c',
    desc: 'What data was captured?',
    filledBy: 'Your case data + eval sidecar quality scores',
  },
  {
    key: 'metrics',
    icon: 'bi-speedometer2',
    title: 'Metric',
    color: '#ca8a04',
    desc: 'How are failures scored at scale?',
    filledBy: 'Fuse engine (aggregates across all cases)',
  },
  {
    key: 'actions',
    icon: 'bi-wrench-adjustable',
    title: 'Improvement Action',
    color: '#16a34a',
    desc: 'What should you fix?',
    filledBy: 'Fuse engine (threshold-triggered recommendations)',
  },
];

/* -------------------------------------------------------------------------- */
/*  Component                                                                 */
/* -------------------------------------------------------------------------- */

export interface FusePipelineProgressProps {
  /**
   * Map of step key → status.  Missing keys default to `pending`.
   * Keys: business_goal, agent_decision, failure_mode, signals, metrics, actions
   */
  steps: Record<string, PipelineStepStatus>;
  /** Overall pipeline label (e.g. scenario name). */
  label?: string;
}

const STATE_BADGE: Record<string, { bg: string; text: string; icon: string }> = {
  complete: { bg: '#16a34a', text: 'Complete', icon: 'bi-check-circle-fill' },
  'in-progress': { bg: '#2563eb', text: 'In Progress...', icon: 'bi-arrow-repeat' },
  pending: { bg: '#6b7280', text: 'Pending', icon: 'bi-clock' },
};

export default function FusePipelineProgress({ steps, label }: FusePipelineProgressProps) {
  const completedCount = STEPS.filter((s) => steps[s.key]?.state === 'complete').length;
  const isRunning = Object.values(steps).some((s) => s.state === 'in-progress');

  return (
    <Card className="mb-4 border-0 shadow-sm">
      <Card.Body className="p-4">
        {/* Header */}
        <div className="d-flex align-items-center justify-content-between mb-2">
          <h5 className="fw-bold mb-0" style={{ color: '#1e3a5f' }}>
            <i className="bi bi-diagram-3 me-2" />
            Pipeline Progress
          </h5>
          <Badge
            bg={isRunning ? 'primary' : completedCount === STEPS.length ? 'success' : 'secondary'}
            className="d-flex align-items-center gap-1"
            style={{ fontSize: '0.78rem' }}
          >
            {isRunning && (
              <span className="spinner-border spinner-border-sm me-1" style={{ width: 12, height: 12 }} />
            )}
            {isRunning ? 'Running...' : completedCount === STEPS.length ? 'Complete' : 'Waiting'}
          </Badge>
        </div>

        {/* Progress bar */}
        <div
          className="rounded overflow-hidden mb-1"
          style={{ height: 8, background: '#e5e7eb' }}
        >
          <div
            className="h-100 rounded"
            style={{
              width: `${(completedCount / STEPS.length) * 100}%`,
              background: isRunning
                ? 'repeating-linear-gradient(45deg, #2563eb, #2563eb 10px, #3b82f6 10px, #3b82f6 20px)'
                : '#16a34a',
              backgroundSize: isRunning ? '28px 28px' : undefined,
              animation: isRunning ? 'fuse-progress-stripe 0.6s linear infinite' : undefined,
              transition: 'width 0.5s ease',
            }}
          />
        </div>
        <small className="text-muted d-block mb-3">
          {completedCount} of {STEPS.length} steps complete
          {label && <> — <strong>{label}</strong></>}
        </small>

        {/* Step cards */}
        <div className="d-flex flex-wrap gap-2">
          {STEPS.map((step) => {
            const status = steps[step.key] || { state: 'pending' as const };
            const badge = STATE_BADGE[status.state];
            const isComplete = status.state === 'complete';
            const isActive = status.state === 'in-progress';

            return (
              <div
                key={step.key}
                className="rounded p-3"
                style={{
                  flex: '1 1 160px',
                  minWidth: 160,
                  background: isActive
                    ? 'linear-gradient(135deg, #1e293b, #0f1a2e)'
                    : isComplete
                      ? '#0c1a2d'
                      : '#1a2332',
                  border: isActive
                    ? `1px solid ${step.color}`
                    : '1px solid rgba(255,255,255,0.08)',
                  color: '#e2e8f0',
                  opacity: status.state === 'pending' ? 0.6 : 1,
                  transition: 'all 0.3s ease',
                }}
              >
                {/* Step header */}
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <div className="d-flex align-items-center">
                    <i className={`bi ${step.icon} me-2`} style={{ color: step.color, fontSize: 16 }} />
                    <strong style={{ fontSize: '0.82rem' }}>{step.title}</strong>
                  </div>
                  <span
                    className="d-inline-flex align-items-center gap-1 rounded-pill px-2 py-0"
                    style={{
                      fontSize: '0.65rem',
                      fontWeight: 600,
                      background: badge.bg,
                      color: '#fff',
                    }}
                  >
                    <i className={`bi ${badge.icon}`} style={{ fontSize: 10 }} />
                    {badge.text}
                  </span>
                </div>

                {/* Description */}
                <p className="mb-1" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {step.desc}
                </p>

                {/* Filled by */}
                <small style={{ fontSize: '0.7rem', color: '#64748b' }}>
                  <i className="bi bi-arrow-return-right me-1" />
                  {status.filledBy || step.filledBy}
                </small>

                {/* Detail line */}
                {status.detail && (
                  <small className="d-block mt-1" style={{ fontSize: '0.7rem', color: isActive ? step.color : '#94a3b8' }}>
                    {status.detail}
                  </small>
                )}
              </div>
            );
          })}
        </div>
      </Card.Body>

      {/* Animated stripe keyframes */}
      <style>{`
        @keyframes fuse-progress-stripe {
          0% { background-position: 0 0; }
          100% { background-position: 28px 0; }
        }
      `}</style>
    </Card>
  );
}
