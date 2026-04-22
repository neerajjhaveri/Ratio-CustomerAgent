/**
 * FuseStudioPage — main evaluation UI for the Ratio Fuse decision-aware metric engine.
 *
 * Loads scenarios + safety options in parallel on mount, provides a JSON editor
 * for case input, and renders metric results via extracted sub-components.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Container from 'react-bootstrap/Container';
import Form from 'react-bootstrap/Form';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Row from 'react-bootstrap/Row';
import Spinner from 'react-bootstrap/Spinner';
import Tooltip from 'react-bootstrap/Tooltip';

import { evaluateScenario, getMockMode, getSafetyOptions, listScenarios, setMockMode } from '../api/fuseClient';
import {
  DiagnosticsPanel,
  FusePipelineProgress,
  MetricsTable,
  RecommendationsPanel,
  ResultsSummary,
  SafetyPromptPanel,
  ThinkingStepper,
} from '../components';
import type { PipelineStepStatus } from '../components';
import { DEFAULT_CASE } from '../constants/fuse';
import type {
  EvaluateScenarioResponse,
  ScenarioCaseInput,
  ScenarioSummary,
  SafetyOptionsResponse,
} from '../types/fuse';

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function FuseStudioPage() {
  // --- Scenario state ---
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedScenario, setSelectedScenario] = useState('');

  // --- Case editor ---
  const [jsonInput, setJsonInput] = useState(JSON.stringify([DEFAULT_CASE], null, 2));
  const [jsonError, setJsonError] = useState<string | null>(null);

  // --- Evaluation result ---
  const [result, setResult] = useState<EvaluateScenarioResponse | null>(null);

  // --- Safety panel ---
  const [safetyOptions, setSafetyOptions] = useState<SafetyOptionsResponse | null>(null);
  const [safetyError, setSafetyError] = useState<string | null>(null);

  // --- UI state ---
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initLoading, setInitLoading] = useState(true);

  // --- Mock mode ---
  const [mockMode, setMockModeState] = useState(false);
  const [mockToggling, setMockToggling] = useState(false);

  // --- Parallel data loading on mount ---
  useEffect(() => {
    let cancelled = false;

    const loadScenarios = async () => {
      try {
        const res = await listScenarios();
        if (cancelled) return;
        setScenarios(res.scenarios);
        if (res.scenarios.length > 0) {
          setSelectedScenario(res.scenarios[0].scenario_id);
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      } finally {
        if (!cancelled) setInitLoading(false);
      }
    };

    const loadSafetyOptions = async () => {
      try {
        const res = await getSafetyOptions();
        if (!cancelled) setSafetyOptions(res);
      } catch {
        if (!cancelled) setSafetyError('Safety service unavailable — prompts panel disabled.');
      }
    };

    // Fire both in parallel — safety failure does NOT block scenarios
    void loadScenarios();
    void loadSafetyOptions();

    // Load mock-mode state (best-effort — toggle stays hidden on error)
    void getMockMode().then((res) => {
      if (!cancelled) setMockModeState(res.mock_mode);
    }).catch(() => { /* mock-mode endpoint unavailable — leave default */ });

    return () => { cancelled = true; };
  }, []);

  const selectedScenarioDetails = useMemo(
    () => scenarios.find((s) => s.scenario_id === selectedScenario),
    [scenarios, selectedScenario],
  );

  // --- JSON validation ---
  const validateJson = useCallback((input: string): ScenarioCaseInput[] | null => {
    try {
      const parsed = JSON.parse(input);
      if (!Array.isArray(parsed)) {
        setJsonError('Input must be a JSON array of case objects (e.g. [{...}])');
        return null;
      }
      for (let i = 0; i < parsed.length; i++) {
        if (!parsed[i].case_id) {
          setJsonError(`Case at index ${i} is missing required field "case_id"`);
          return null;
        }
      }
      setJsonError(null);
      return parsed as ScenarioCaseInput[];
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setJsonError(`Invalid JSON: ${msg}`);
      return null;
    }
  }, []);

  const handleJsonChange = useCallback((value: string) => {
    setJsonInput(value);
    // Optimistic: clear the error indicator as soon as the JSON parses
    // successfully again. Parse failures are silently ignored here because
    // validation is run explicitly when the user clicks "Evaluate Cases".
    try {
      JSON.parse(value);
      setJsonError(null);
    } catch {
      // No-op — keep previous error until the next explicit validation
    }
  }, []);

  // --- Evaluate handler ---
  const handleRunScenario = useCallback(async () => {
    setError(null);
    const cases = validateJson(jsonInput);
    if (!cases) return;

    setLoading(true);
    setResult(null);
    try {
      const response = await evaluateScenario({
        scenario_id: selectedScenario,
        include_case_diagnostics: true,
        cases,
      });
      setResult(response);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [jsonInput, selectedScenario, validateJson]);

  // --- Mock mode toggle ---
  const handleMockToggle = useCallback(async () => {
    setMockToggling(true);
    try {
      const res = await setMockMode(!mockMode);
      setMockModeState(res.mock_mode);
    } catch (err) {
      setError(String(err));
    } finally {
      setMockToggling(false);
    }
  }, [mockMode]);

  // --- Thinking stepper logic ---
  const currentStep = result
    ? (result.recommendations.length > 0 ? 6 : 5)
    : loading ? 4 : selectedScenario ? 1 : 0;

  // --- Pipeline progress steps ---
  const pipelineSteps: Record<string, PipelineStepStatus> = (() => {
    if (result) {
      const hasRecs = result.recommendations.length > 0;
      return {
        business_goal:  { state: 'complete', detail: selectedScenarioDetails?.name, filledBy: 'Scenario YAML' },
        agent_decision: { state: 'complete', filledBy: 'Scenario YAML (derived signals)' },
        failure_mode:   { state: 'complete', detail: `${result.diagnostics?.length ?? 0} cases checked`, filledBy: 'Fuse engine (conditions per case)' },
        signals:        { state: 'complete', filledBy: 'Your case data + eval sidecar' },
        metrics:        { state: 'complete', detail: `${result.metrics.length} metrics computed`, filledBy: 'Fuse engine (aggregated)' },
        actions:        { state: hasRecs ? 'complete' : 'pending', detail: hasRecs ? `${result.recommendations.length} recommendations` : 'No thresholds breached', filledBy: 'Fuse engine (threshold triggers)' },
      };
    }
    if (loading) {
      return {
        business_goal:  { state: 'complete', detail: selectedScenarioDetails?.name, filledBy: 'Scenario YAML' },
        agent_decision: { state: 'complete', filledBy: 'Scenario YAML (derived signals)' },
        failure_mode:   { state: 'in-progress', detail: 'Evaluating failure conditions...', filledBy: 'Fuse engine' },
        signals:        { state: 'in-progress', detail: 'Calling eval sidecar...', filledBy: 'Your case data + eval sidecar' },
        metrics:        { state: 'pending' },
        actions:        { state: 'pending' },
      };
    }
    if (selectedScenario) {
      return {
        business_goal:  { state: 'complete', detail: selectedScenarioDetails?.name, filledBy: 'Scenario YAML' },
        agent_decision: { state: 'complete', filledBy: 'Scenario YAML' },
        failure_mode:   { state: 'pending' },
        signals:        { state: 'pending' },
        metrics:        { state: 'pending' },
        actions:        { state: 'pending' },
      };
    }
    return {} as Record<string, PipelineStepStatus>;
  })();

  // --- Loading state ---
  if (initLoading) {
    return (
      <Container className="py-5 text-center">
        <Spinner animation="border" className="me-2" />
        Loading Fuse Studio...
      </Container>
    );
  }

  return (
    <Container className="py-4" style={{ maxWidth: 1100 }}>
      {/* Page Header */}
      <div className="mb-3 d-flex justify-content-between align-items-start">
        <div>
          <h1 className="fw-bold mb-1" style={{ color: '#1e3a5f' }}>
            <i className="bi bi-diagram-3 me-2" />
            Fuse Studio
          </h1>
          <p className="text-muted mb-0">
            Define scenarios, evaluate decision-aware metrics, and get actionable recommendations to improve agent systems.
          </p>
        </div>
        <div className="d-flex align-items-center gap-2 mt-1">
          {mockMode && <Badge bg="warning" text="dark">MOCK</Badge>}
          <Form.Check
            type="switch"
            id="mock-mode-toggle"
            label="Mock Mode"
            checked={mockMode}
            disabled={mockToggling}
            onChange={handleMockToggle}
            className="mb-0"
          />
        </div>
      </div>

      {/* Thinking Model Stepper */}
      <ThinkingStepper currentStep={currentStep} />

      {/* Pipeline Progress */}
      {selectedScenario && (
        <FusePipelineProgress
          steps={pipelineSteps}
          label={selectedScenarioDetails?.name}
        />
      )}

      {/* Global Error Banner */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Step 1-2: Select Scenario + Provide Cases */}
      <Card className="mb-4 border-0 shadow-sm">
        <Card.Header className="bg-white border-bottom">
          <div className="d-flex align-items-center">
            <span className="d-inline-flex align-items-center justify-content-center rounded-circle me-2"
              style={{ width: 24, height: 24, background: '#2563eb', color: '#fff', fontSize: '0.75rem', fontWeight: 700 }}>1</span>
            <strong>Select a Scenario</strong>
            <small className="text-muted ms-2">— Define the business goal and agent decision to evaluate</small>
          </div>
        </Card.Header>
        <Card.Body>
          <Row className="g-3">
            <Col md={8}>
              <Form.Group>
                <Form.Label className="fw-semibold">Scenario</Form.Label>
                <Form.Select value={selectedScenario} onChange={(e) => setSelectedScenario(e.target.value)}>
                  {scenarios.map((s) => (
                    <option key={s.scenario_id} value={s.scenario_id}>{s.name}</option>
                  ))}
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={4} className="d-flex align-items-end">
              <Button onClick={handleRunScenario} disabled={loading || !selectedScenario} className="w-100" size="lg">
                {loading ? (
                  <><Spinner animation="border" size="sm" className="me-2" />Evaluating...</>
                ) : (
                  <><i className="bi bi-play-fill me-1" />Evaluate Cases</>
                )}
              </Button>
            </Col>
          </Row>

          {/* Scenario info */}
          {selectedScenarioDetails && (
            <div className="mt-2 p-2 rounded" style={{ background: '#f8fafc', fontSize: '0.85rem' }}>
              <p className="mb-1 text-muted">{selectedScenarioDetails.description}</p>
              <div className="d-flex flex-wrap gap-1">
                <small className="text-muted fw-semibold me-1">Metrics:</small>
                {selectedScenarioDetails.supported_metrics.map((m) => (
                  <Badge key={m} bg="light" text="dark" style={{ fontSize: '0.7rem' }}>{m}</Badge>
                ))}
              </div>
            </div>
          )}

          <Form.Group className="mt-3">
            <div className="d-flex align-items-center justify-content-between">
              <div className="d-flex align-items-center">
                <span className="d-inline-flex align-items-center justify-content-center rounded-circle me-2"
                  style={{ width: 22, height: 22, background: '#ea580c', color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>2</span>
                <Form.Label className="fw-semibold mb-0">Provide Cases with Observable Signals</Form.Label>
              </div>
              <OverlayTrigger
                placement="left"
                overlay={
                  <Tooltip>
                    Each case represents one agent interaction. Include: case_id (required),
                    query/answer (for AI quality scoring), and signals (the agent's decisions like
                    send_justified, escalated, routing_correct — these feed the failure mode engine).
                  </Tooltip>
                }
              >
                <i className="bi bi-question-circle text-muted" style={{ cursor: 'help' }} />
              </OverlayTrigger>
            </div>
            <Form.Control
              as="textarea"
              rows={14}
              value={jsonInput}
              onChange={(e) => handleJsonChange(e.target.value)}
              isInvalid={!!jsonError}
              style={{ fontFamily: 'Consolas, "Courier New", monospace', fontSize: '0.82rem' }}
            />
            {jsonError && (
              <Form.Control.Feedback type="invalid">
                <i className="bi bi-exclamation-triangle me-1" />{jsonError}
              </Form.Control.Feedback>
            )}
          </Form.Group>
        </Card.Body>
      </Card>

      {/* Evaluation Results */}
      {result && (
        <>
          <ResultsSummary result={result} />
          <MetricsTable metrics={result.metrics} />
          <RecommendationsPanel recommendations={result.recommendations} />
          {result.diagnostics && <DiagnosticsPanel diagnostics={result.diagnostics} />}
        </>
      )}

      {/* AI Safety Prompt Generator */}
      <SafetyPromptPanel
        safetyOptions={safetyOptions}
        safetyError={safetyError}
        onError={(msg) => setError(msg || null)}
      />
    </Container>
  );
}
