import Badge from 'react-bootstrap/Badge';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import { useNavigate } from 'react-router-dom';

/* -------------------------------------------------------------------------- */
/*  Bucket definitions – each bucket explains what fills it, where the data   */
/*  comes from, and what Fuse can auto-generate if you only supply the first  */
/*  two buckets (Business Goal + Agent Decision).                             */
/* -------------------------------------------------------------------------- */

const BUCKETS = [
  {
    icon: 'bi-bullseye',
    title: 'Business Goal',
    color: '#2563eb',
    question: 'What business outcome matters most?',
    filled_by: 'You (the team)',
    examples: [
      'Customer satisfaction (CSAT)',
      'First-contact resolution rate',
      'Containment rate (no escalation)',
      'Mean time to resolution (MTTR)',
      'Agent accuracy / answer correctness',
    ],
    how: 'Start every conversation here. Ask your partner or customer: "What happens when your agent gets it wrong?" The answer is your business goal.',
    auto: false,
    tip: 'This is always your input. Fuse cannot guess what matters to your business — but everything downstream flows from this answer.',
  },
  {
    icon: 'bi-signpost-split',
    title: 'Agent Decision',
    color: '#7c3aed',
    question: 'What decisions does the agent pipeline make?',
    filled_by: 'You (from your pipeline design)',
    examples: [
      'Send response / hold back',
      'Escalate to human / contain',
      'Route to specialist team',
      'Clarify before answering',
      'Fallback to safe response',
      'Override quality warning',
    ],
    how: 'Map the decision points in your agent pipeline. Each branch is a point where the system can be right or wrong.',
    auto: false,
    tip: 'Supply the business goal and agent decisions — Fuse derives everything below automatically from your scenario YAML.',
  },
  {
    icon: 'bi-exclamation-triangle',
    title: 'Failure Mode',
    color: '#dc2626',
    question: 'What does it look like when a decision goes wrong?',
    filled_by: 'Fuse (auto-derived from scenario YAML)',
    examples: [
      'Unjustified send — agent sent despite low quality',
      'Missed escalation — should have escalated but didn\'t',
      'Wrong routing — case sent to wrong specialist',
      'Missing clarification — answered without enough info',
      'Unnecessary fallback — used safe response when not needed',
      'False override — ignored warning without justification',
    ],
    how: 'Fuse defines failure modes as boolean conditions over your signals. Each condition names a specific way the system failed.',
    auto: true,
    tip: 'You define these in YAML scenario files, or Fuse suggests them from your business goal + decisions. Each failure mode maps to a detectable condition.',
  },
  {
    icon: 'bi-broadcast',
    title: 'Observable Signals',
    color: '#ea580c',
    question: 'What data can we actually measure?',
    filled_by: 'Multiple sources (see below)',
    examples: [
      'Agent verdict & confidence score',
      'Quality eval scores (fluency, coherence, groundedness)',
      'Prompt injection detection results',
      'AI safety evaluators (harm, fairness, jailbreak)',
      'Trajectory / multi-turn evaluations',
      'Routing evaluation scores',
      'Agent behavior analyzers',
      'Pipeline telemetry & traces',
      'Latency, token counts, tool call logs',
    ],
    how: 'This is the richest bucket. Signals come from eval metrics, telemetry, traces, safety evaluators, agent analyzers, trajectory evaluations, and routing evaluations.',
    auto: true,
    tip: null, // Special handling — this bucket gets expanded detail
    signalSources: [
      { name: 'Eval Metrics', icon: 'bi-clipboard-data', desc: 'Content quality scores — fluency, coherence, relevance, groundedness, completeness, similarity.' },
      { name: 'Pipeline Telemetry', icon: 'bi-activity', desc: 'Latency, token usage, tool calls, retry counts, model version — from your agent runtime.' },
      { name: 'Traces & Logs', icon: 'bi-journal-text', desc: 'Distributed traces across agent steps — shows the full decision path and where it branched.' },
      { name: 'Prompt Injection Evaluators', icon: 'bi-shield-exclamation', desc: 'Detects prompt injection attempts and whether the agent was vulnerable or resilient.' },
      { name: 'AI Safety Evaluators', icon: 'bi-shield-check', desc: 'Harm, fairness, jailbreak, self-harm, violence, hate — risk categories scored per interaction.' },
      { name: 'Agent / Trajectory Evals', icon: 'bi-bezier2', desc: 'Multi-turn trajectory evaluation — did the agent follow the right sequence of steps?' },
      { name: 'Routing Evaluations', icon: 'bi-signpost-2', desc: 'Was the case routed to the correct team, skill, or sub-agent? Routing accuracy signals.' },
    ],
    signalNote: 'The more signals you supply, the richer your decision-aware metrics become. If you supply nothing, Fuse uses only the base eval quality scores. Each additional signal source adds a new dimension of understanding to your metrics.',
  },
  {
    icon: 'bi-speedometer2',
    title: 'Metric',
    color: '#ca8a04',
    question: 'How do we measure the failures at scale?',
    filled_by: 'Fuse (auto-computed from signals + failure modes)',
    examples: [
      'Unjustified Send Rate — % of cases sent despite low quality',
      'Escalation Miss Rate — % that should have escalated but didn\'t',
      'Agent-FQR Disagreement Rate — agent vs. expert agreement',
      'Routing Accuracy — % correctly routed cases',
      'Containment Rate — % resolved without escalation',
      'Average confidence at decision point',
    ],
    how: 'Fuse aggregates failure modes into rates, counts, and averages. Each metric has a threshold, status (good/warning/bad), and direction (lower-is-better or higher-is-better).',
    auto: true,
    tip: 'Metrics are defined in YAML with expressions over signals. Fuse computes them across all your cases and compares against the thresholds you set.',
  },
  {
    icon: 'bi-wrench-adjustable',
    title: 'Improvement Action',
    color: '#16a34a',
    question: 'What should we actually fix?',
    filled_by: 'Fuse (recommendations triggered by metric thresholds)',
    examples: [
      'Tune the send/hold confidence threshold',
      'Add escalation logic for low-quality overrides',
      'Improve routing with better intent classification',
      'Add clarification step before answering ambiguous queries',
      'Adjust safety sensitivity for false positives',
      'Retrain on cases where rewrite was required',
    ],
    how: 'Each metric maps to a specific improvement action. When a metric breaches its threshold, Fuse surfaces the recommendation with priority and next steps.',
    auto: true,
    tip: 'This is where decision-aware metrics pay off. Instead of "your fluency score is 3.2", you get "18% of sends were unjustified → tune the confidence threshold for the send decision".',
  },
];

/* -------------------------------------------------------------------------- */
/*  Component                                                                 */
/* -------------------------------------------------------------------------- */

function FuseLandingPage() {
  const navigate = useNavigate();

  return (
    <Container fluid className="py-4 px-4" style={{ maxWidth: 1200 }}>
      {/* Hero */}
      <div className="text-center mb-4">
        <img src="/RATIO.svg" alt="Ratio AI" style={{ height: 56, marginBottom: 12 }} />
        <h1 className="fw-bold mb-2" style={{ fontSize: '2rem', color: '#1e3a5f' }}>
          Ratio AI Fuse
        </h1>
        <p className="text-muted mb-1" style={{ fontSize: '1.1rem', maxWidth: 700, margin: '0 auto' }}>
          The decision-intelligence layer for agent systems.
          Move beyond scoring answers — understand whether your agent pipeline
          made the <strong>right decision</strong> at the <strong>right time</strong>.
        </p>
        <Badge bg="primary" className="mt-2" style={{ fontSize: '0.8rem' }}>
          Making Agents Better Through Decision-Aware Metrics
        </Badge>
      </div>

      {/* Philosophy callout */}
      <Card className="mb-4 border-0 shadow-sm" style={{ borderLeft: '4px solid #7c3aed' }}>
        <Card.Body className="py-3 px-4">
          <p className="mb-0" style={{ fontSize: '0.92rem', color: '#374151', lineHeight: 1.6 }}>
            <i className="bi bi-lightbulb me-2" style={{ color: '#7c3aed' }} />
            <strong>Don't start by asking which eval metrics to run.</strong> Start by understanding the
            business outcomes that matter, the scenarios where agent decisions count, what failure looks
            like, and what signals are already available. That gives you the inputs to build{' '}
            <strong>decision-aware metrics</strong> — not just raw quality scores.
          </p>
        </Card.Body>
      </Card>

      {/* Pipeline Progress — bucket cards */}
      <Card className="mb-4 border-0 shadow-sm">
        <Card.Body className="p-4">
          <div className="d-flex align-items-center justify-content-between mb-1">
            <h5 className="fw-bold mb-0" style={{ color: '#1e3a5f' }}>
              <i className="bi bi-diagram-3 me-2" />
              The Fuse Pipeline
            </h5>
            <Badge bg="light" text="dark" style={{ fontSize: '0.75rem' }}>
              6 buckets — supply the first 2, Fuse fills the rest
            </Badge>
          </div>
          <p className="text-muted mb-4" style={{ fontSize: '0.88rem' }}>
            Each card below is a "bucket" in the Fuse thinking model. You fill the first two
            (Business Goal + Agent Decision), and Fuse derives failure modes, computes metrics,
            and generates improvement actions from the observable signals you provide.
          </p>

          {/* Progress bar */}
          <div className="d-flex align-items-center mb-4" style={{ gap: 4 }}>
            {BUCKETS.map((b, i) => (
              <div key={b.title} className="d-flex align-items-center" style={{ flex: 1 }}>
                <div
                  style={{
                    height: 6,
                    flex: 1,
                    borderRadius: 3,
                    background: b.color,
                    opacity: b.auto ? 0.5 : 1,
                  }}
                />
                {i < BUCKETS.length - 1 && (
                  <i className="bi bi-chevron-right mx-1" style={{ fontSize: 10, color: '#94a3b8' }} />
                )}
              </div>
            ))}
          </div>

          {/* Bucket cards */}
          <Row className="g-3">
            {BUCKETS.map((bucket, index) => (
              <Col key={bucket.title} md={6} lg={4}>
                <Card
                  className="h-100 border-0 shadow-sm"
                  style={{ borderTop: `3px solid ${bucket.color}` }}
                >
                  <Card.Body className="p-3">
                    {/* Header */}
                    <div className="d-flex align-items-start mb-2">
                      <div
                        className="d-inline-flex align-items-center justify-content-center rounded-circle me-2 flex-shrink-0"
                        style={{ width: 36, height: 36, background: bucket.color, color: '#fff', fontSize: 16 }}
                      >
                        <i className={`bi ${bucket.icon}`} />
                      </div>
                      <div className="flex-grow-1">
                        <div className="d-flex align-items-center justify-content-between">
                          <h6 className="fw-bold mb-0" style={{ fontSize: '0.88rem', color: bucket.color }}>
                            {index + 1}. {bucket.title}
                          </h6>
                          <Badge
                            bg={bucket.auto ? 'success' : 'primary'}
                            style={{ fontSize: '0.65rem' }}
                          >
                            {bucket.auto ? 'Auto' : 'You supply'}
                          </Badge>
                        </div>
                        <small className="text-muted" style={{ fontSize: '0.75rem' }}>
                          Filled by: {bucket.filled_by}
                        </small>
                      </div>
                    </div>

                    {/* Question */}
                    <p className="fw-semibold mb-2" style={{ fontSize: '0.82rem', color: '#374151' }}>
                      {bucket.question}
                    </p>

                    {/* Examples */}
                    <div className="mb-2">
                      {bucket.examples.map((ex) => (
                        <div key={ex} className="d-flex align-items-start mb-1" style={{ fontSize: '0.78rem' }}>
                          <i className="bi bi-check2 me-1 flex-shrink-0" style={{ color: bucket.color, marginTop: 2 }} />
                          <span className="text-muted">{ex}</span>
                        </div>
                      ))}
                    </div>

                    {/* How it's generated */}
                    <div className="p-2 rounded mb-2" style={{ background: '#f8fafc', fontSize: '0.78rem' }}>
                      <strong style={{ color: '#475569' }}>How:</strong>{' '}
                      <span className="text-muted">{bucket.how}</span>
                    </div>

                    {/* Tip or signal sources */}
                    {bucket.tip && (
                      <small className="d-block text-muted" style={{ fontSize: '0.75rem', lineHeight: 1.4 }}>
                        <i className="bi bi-info-circle me-1" style={{ color: bucket.color }} />
                        {bucket.tip}
                      </small>
                    )}

                    {/* Special expanded section for Observable Signals */}
                    {bucket.signalSources && (
                      <div className="mt-2">
                        <small className="fw-semibold d-block mb-1" style={{ fontSize: '0.76rem', color: '#475569' }}>
                          Signal sources that fill this bucket:
                        </small>
                        {bucket.signalSources.map((src) => (
                          <div
                            key={src.name}
                            className="d-flex align-items-start mb-1 p-1 rounded"
                            style={{ background: '#fff7ed', fontSize: '0.73rem' }}
                          >
                            <i className={`bi ${src.icon} me-1 flex-shrink-0`} style={{ color: '#ea580c', marginTop: 1, fontSize: 12 }} />
                            <span>
                              <strong style={{ color: '#9a3412' }}>{src.name}</strong>
                              <span className="text-muted"> — {src.desc}</span>
                            </span>
                          </div>
                        ))}
                        <small className="d-block mt-1 text-muted" style={{ fontSize: '0.73rem', lineHeight: 1.4 }}>
                          <i className="bi bi-info-circle me-1" style={{ color: '#ea580c' }} />
                          {bucket.signalNote}
                        </small>
                      </div>
                    )}
                  </Card.Body>
                </Card>
              </Col>
            ))}
          </Row>
        </Card.Body>
      </Card>

      {/* Three-column explanation */}
      <Row className="g-3 mb-4">
        <Col md={4}>
          <Card className="h-100 border-0 shadow-sm">
            <Card.Body>
              <div className="d-flex align-items-center mb-2">
                <i className="bi bi-clipboard-data me-2" style={{ fontSize: 20, color: '#2563eb' }} />
                <h6 className="fw-bold mb-0">Traditional Eval Metrics</h6>
              </div>
              <p className="text-muted mb-2" style={{ fontSize: '0.85rem' }}>
                Score the <em>content</em> — groundedness, relevance, coherence, safety, fluency.
              </p>
              <small className="text-muted">
                <strong>Limitation:</strong> Tells you <em>what</em> quality the answer had,
                not <em>whether the system acted correctly</em> given its signals.
              </small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="h-100 border-0 shadow-sm" style={{ borderLeft: '3px solid #7c3aed' }}>
            <Card.Body>
              <div className="d-flex align-items-center mb-2">
                <i className="bi bi-lightning-charge me-2" style={{ fontSize: 20, color: '#7c3aed' }} />
                <h6 className="fw-bold mb-0">Decision-Aware Metrics</h6>
              </div>
              <p className="text-muted mb-2" style={{ fontSize: '0.85rem' }}>
                Score the <em>system judgment</em> — did the pipeline override warnings? Was the
                override justified? Which failure modes are causing harm?
              </p>
              <small style={{ color: '#7c3aed' }}>
                <strong>This is Fuse.</strong> Composite metrics built from eval signals + pipeline telemetry.
              </small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="h-100 border-0 shadow-sm">
            <Card.Body>
              <div className="d-flex align-items-center mb-2">
                <i className="bi bi-arrow-repeat me-2" style={{ fontSize: 20, color: '#16a34a' }} />
                <h6 className="fw-bold mb-0">Improvement Actions</h6>
              </div>
              <p className="text-muted mb-2" style={{ fontSize: '0.85rem' }}>
                Each metric maps to a concrete action — tune prompts, adjust thresholds,
                improve routing, add fallback, fix escalation logic.
              </p>
              <small className="text-muted">
                <strong>Goal:</strong> Move from measuring outputs to improving agent behavior.
              </small>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* CTA */}
      <div className="text-center">
        <button
          className="btn btn-primary btn-lg px-4"
          onClick={() => navigate('/fuse/studio')}
        >
          <i className="bi bi-play-circle me-2" />
          Open Fuse Studio
        </button>
        <p className="text-muted mt-2" style={{ fontSize: '0.8rem' }}>
          Define scenarios, evaluate decision-aware metrics, and get actionable recommendations.
        </p>
      </div>
    </Container>
  );
}

export default FuseLandingPage;
