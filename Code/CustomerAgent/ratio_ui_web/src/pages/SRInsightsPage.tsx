import { useState, type FormEvent } from 'react';
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Badge from 'react-bootstrap/Badge';
import Alert from 'react-bootstrap/Alert';
import Accordion from 'react-bootstrap/Accordion';
import Spinner from 'react-bootstrap/Spinner';
import { TimeRangeFilter, ProductNameCombobox } from '../components';
import {
  summarizeOutage,
  summarizeProduct,
  getHealth,
  previewOutageQuery,
  previewOutagePrompts,
  previewProductQuery,
} from '../api/srInsightsClient';
import type {
  OutageSummarizeResponse,
  ProductSummarizeResponse,
  HealthResponse,
  QueryPreviewResponse,
  OutagePromptsPreviewResponse,
  PromptStage,
} from '../types/srInsights';

type ActiveTab = 'outage' | 'product';

export default function SRInsightsPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('outage');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  /* ---------- outage state ---------- */
  const [outageId, setOutageId] = useState('');
  const [outStartDate, setOutStartDate] = useState('');
  const [outEndDate, setOutEndDate] = useState('');
  const [serviceName, setServiceName] = useState('');
  const [outMaxSrs, setOutMaxSrs] = useState(500);
  const [includeExecSummary, setIncludeExecSummary] = useState(true);
  const [includeClusters, setIncludeClusters] = useState(true);
  const [outageResult, setOutageResult] = useState<OutageSummarizeResponse | null>(null);

  /* ---------- product state ---------- (time range replaces old date inputs) */
  /* Note: prodStartDate / prodEndDate below are reused for the product tab */
  /* They now receive ISO strings from the TimeRangeFilter component */


  /* ---------- preview state ---------- */
  const [kqlPreview, setKqlPreview] = useState<QueryPreviewResponse | null>(null);
  const [kqlPreviewLoading, setKqlPreviewLoading] = useState(false);
  const [promptsPreview, setPromptsPreview] = useState<OutagePromptsPreviewResponse | null>(null);
  const [promptsPreviewLoading, setPromptsPreviewLoading] = useState(false);
  const [productKqlPreview, setProductKqlPreview] = useState<QueryPreviewResponse | null>(null);
  const [productKqlPreviewLoading, setProductKqlPreviewLoading] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  /* ---------- product state ---------- */
  const [productName, setProductName] = useState('');
  const [supportTopic, setSupportTopic] = useState('');
  const [prodStartDate, setProdStartDate] = useState('');
  const [prodEndDate, setProdEndDate] = useState('');
  const [alertType, setAlertType] = useState('Allsev');
  const [prodMaxSrs, setProdMaxSrs] = useState(500);
  const [productResult, setProductResult] = useState<ProductSummarizeResponse | null>(null);

  /* ---------------------------------------------------------------- */
  const checkHealth = async () => {
    try {
      setHealth(await getHealth());
    } catch (e) {
      setHealth(null);
      setError(String(e));
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback(`Copied ${label}`);
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch {
      setCopyFeedback(`Copy ${label} failed — select text manually`);
      setTimeout(() => setCopyFeedback(null), 3000);
    }
  };

  const handleKqlPreview = async () => {
    if (!outageId) { setError('Enter an Outage ID to preview the query'); return; }
    setError(null);
    setKqlPreview(null);
    setKqlPreviewLoading(true);
    try {
      setKqlPreview(await previewOutageQuery(Number(outageId)));
    } catch (err) {
      setError(String(err));
    } finally {
      setKqlPreviewLoading(false);
    }
  };

  const handlePromptsPreview = async () => {
    if (!outageId) { setError('Enter an Outage ID to preview prompts'); return; }
    setError(null);
    setPromptsPreview(null);
    setPromptsPreviewLoading(true);
    try {
      setPromptsPreview(await previewOutagePrompts(Number(outageId)));
    } catch (err) {
      setError(String(err));
    } finally {
      setPromptsPreviewLoading(false);
    }
  };

  const handleProductKqlPreview = async () => {
    if (!productName || !prodStartDate || !prodEndDate) {
      setError('Fill in product name and dates to preview the query');
      return;
    }
    setError(null);
    setProductKqlPreview(null);
    setProductKqlPreviewLoading(true);
    try {
      setProductKqlPreview(await previewProductQuery(productName, prodStartDate, prodEndDate, alertType));
    } catch (err) {
      setError(String(err));
    } finally {
      setProductKqlPreviewLoading(false);
    }
  };

  const buildCompleteConversation = (stage: PromptStage) =>
    `=== SYSTEM MESSAGE ===\n${stage.system_message}\n\n=== USER MESSAGE (${stage.stage_name}) ===\n${stage.user_message}\n\n=== PARAMETERS ===\nModel: ${stage.model}\nTemperature: ${stage.temperature}\nMax Tokens: ${stage.max_tokens}`;

  const handleOutage = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setOutageResult(null);
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        max_srs: outMaxSrs,
        include_faq: includeExecSummary,
        include_executive_summary: includeExecSummary,
        include_clusters: includeClusters,
      };
      if (outageId) body.outage_id = Number(outageId);
      else { body.start_date = outStartDate; body.end_date = outEndDate; }
      if (serviceName) body.service_name = serviceName;
      setOutageResult(await summarizeOutage(body as any));
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleProduct = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setProductResult(null);
    setLoading(true);
    try {
      setProductResult(
        await summarizeProduct({
          product_name: productName,
          support_topic: supportTopic || undefined,
          start_date: prodStartDate,
          end_date: prodEndDate,
          alert_type: alertType,
          max_srs: prodMaxSrs,
        }),
      );
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  /* ---------------------------------------------------------------- */
  return (
    <Container className="py-4" style={{ maxWidth: 960 }}>
      <h1>Service Impact Customers Tell Us &mdash; by RATIO</h1>
      <p className="text-muted">Summarize Azure service requests by outage or product.</p>

      {/* Health */}
      <div className="mb-3">
        <Button variant="success" size="sm" onClick={checkHealth}>
          <i className="bi bi-heart-pulse me-1" /> Check service health
        </Button>
        {health && (
          <span className="ms-3 text-success fw-semibold">
            {health.service} — {health.status} (v{health.version})
          </span>
        )}
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}

      {/* Tabs */}
      <Tabs activeKey={activeTab} onSelect={(k) => setActiveTab(k as ActiveTab)} className="mb-4">
        <Tab eventKey="outage" title="Outage-based Review">
          <Form onSubmit={handleOutage}>
            <Row className="g-3">
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Outage / Incident ID</Form.Label>
                  <Form.Control type="number" value={outageId} onChange={(e) => setOutageId(e.target.value)} placeholder="e.g. 739503040" />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Azure Service Name (optional)</Form.Label>
                  <Form.Control value={serviceName} onChange={(e) => setServiceName(e.target.value)} />
                </Form.Group>
              </Col>
              <Col md={12}>
                <TimeRangeFilter
                  label="Outage"
                  startDate={outStartDate}
                  endDate={outEndDate}
                  onChange={({ startDate, endDate }) => { setOutStartDate(startDate); setOutEndDate(endDate); }}
                />
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Max SRs</Form.Label>
                  <Form.Control type="number" min={1} max={5000} value={outMaxSrs} onChange={(e) => setOutMaxSrs(Number(e.target.value))} />
                </Form.Group>
              </Col>
              <Col md={6} className="d-flex align-items-end gap-3 flex-wrap">
                <Form.Check label="Executive Summary" checked={includeExecSummary} onChange={(e) => setIncludeExecSummary(e.target.checked)} />
                <Form.Check label="Clusters" checked={includeClusters} onChange={(e) => setIncludeClusters(e.target.checked)} />
              </Col>
            </Row>
            <div className="mt-3 d-flex gap-2 flex-wrap">
              <Button type="submit" disabled={loading}>
                {loading ? <><Spinner animation="border" size="sm" className="me-2" />Processing...</> : 'Summarize Outage'}
              </Button>
              <Button variant="outline-secondary" size="sm" onClick={handleKqlPreview} disabled={kqlPreviewLoading}>
                {kqlPreviewLoading ? <Spinner animation="border" size="sm" /> : <><i className="bi bi-code-slash me-1" />Preview KQL Query</>}
              </Button>
              <Button variant="outline-secondary" size="sm" onClick={handlePromptsPreview} disabled={promptsPreviewLoading}>
                {promptsPreviewLoading ? <Spinner animation="border" size="sm" /> : <><i className="bi bi-chat-dots me-1" />Preview LLM Prompts</>}
              </Button>
            </div>
            {copyFeedback && <small className="text-success mt-1 d-block">{copyFeedback}</small>}
          </Form>

          {/* KQL Query Preview */}
          {kqlPreview && (
            <Card className="mt-3 border-secondary">
              <Card.Header className="d-flex justify-content-between align-items-center bg-dark text-light">
                <span><i className="bi bi-code-slash me-2" />KQL Query Preview</span>
                <Button variant="outline-light" size="sm" onClick={() => copyToClipboard(kqlPreview.query, 'KQL Query')}>
                  <i className="bi bi-clipboard me-1" />Copy
                </Button>
              </Card.Header>
              <Card.Body>
                <small className="text-muted d-block mb-2">
                  Cluster: <code>{kqlPreview.cluster}</code> &mdash; Database: <code>{kqlPreview.database}</code>
                </small>
                <pre className="bg-light p-3 rounded" style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', maxHeight: 400, overflow: 'auto' }}>
                  {kqlPreview.query}
                </pre>
              </Card.Body>
            </Card>
          )}

          {/* LLM Prompt Preview */}
          {promptsPreview && (
            <Card className="mt-3 border-secondary">
              <Card.Header className="bg-dark text-light">
                <i className="bi bi-chat-dots me-2" />LLM Prompt Preview
                <small className="ms-2 text-light opacity-75">({promptsPreview.sr_count} SRs fetched)</small>
              </Card.Header>
              <Card.Body>
                <Alert variant="info" className="py-2 small mb-3">{promptsPreview.note}</Alert>
                <Accordion>
                  {promptsPreview.stages.map((stage, idx) => (
                    <Accordion.Item eventKey={String(idx)} key={idx}>
                      <Accordion.Header>
                        <strong>{stage.stage_name}</strong>
                        <small className="text-muted ms-2">{stage.description}</small>
                      </Accordion.Header>
                      <Accordion.Body>
                        {/* System Message */}
                        <div className="mb-3">
                          <div className="d-flex justify-content-between align-items-center mb-1">
                            <strong className="text-primary">System Message</strong>
                            <Button variant="outline-primary" size="sm" onClick={() => copyToClipboard(stage.system_message, 'System Message')}>
                              <i className="bi bi-clipboard me-1" />Copy
                            </Button>
                          </div>
                          <pre className="bg-light p-3 rounded" style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem', maxHeight: 300, overflow: 'auto' }}>
                            {stage.system_message}
                          </pre>
                        </div>

                        {/* User Message */}
                        <div className="mb-3">
                          <div className="d-flex justify-content-between align-items-center mb-1">
                            <strong className="text-success">User Message</strong>
                            <Button variant="outline-success" size="sm" onClick={() => copyToClipboard(stage.user_message, 'User Message')}>
                              <i className="bi bi-clipboard me-1" />Copy
                            </Button>
                          </div>
                          <pre className="bg-light p-3 rounded" style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem', maxHeight: 400, overflow: 'auto' }}>
                            {stage.user_message}
                          </pre>
                        </div>

                        {/* Complete Conversation */}
                        <div>
                          <div className="d-flex justify-content-between align-items-center mb-1">
                            <strong className="text-secondary">Complete Conversation</strong>
                            <Button variant="outline-secondary" size="sm" onClick={() => copyToClipboard(buildCompleteConversation(stage), 'Complete Conversation')}>
                              <i className="bi bi-clipboard me-1" />Copy
                            </Button>
                          </div>
                          <pre className="bg-light p-3 rounded" style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem', maxHeight: 500, overflow: 'auto' }}>
                            {buildCompleteConversation(stage)}
                          </pre>
                        </div>

                        <div className="mt-2 text-muted small">
                          Model: <code>{stage.model}</code> &middot; Temperature: {stage.temperature} &middot; Max tokens: {stage.max_tokens}
                        </div>
                      </Accordion.Body>
                    </Accordion.Item>
                  ))}
                </Accordion>
              </Card.Body>
            </Card>
          )}

          {outageResult && (
            <div className="mt-4">
              <Card className="mb-3">
                <Card.Body><strong>Processed:</strong> {outageResult.total_srs_processed} SRs</Card.Body>
              </Card>

              {outageResult.executive_summary && (
                <Card className="mb-3">
                  <Card.Body>
                    <Card.Title>Executive Summary</Card.Title>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{outageResult.executive_summary}</p>
                  </Card.Body>
                </Card>
              )}

              {outageResult.faq && outageResult.faq.length > 0 && (
                <Card className="mb-3">
                  <Card.Body>
                    <Card.Title>FAQ</Card.Title>
                    <Accordion>
                      {outageResult.faq.map((f, i) => (
                        <Accordion.Item eventKey={String(i)} key={i}>
                          <Accordion.Header>{f.question}</Accordion.Header>
                          <Accordion.Body>
                            {f.answer && (
                              <p style={{ whiteSpace: 'pre-wrap' }}>{f.answer}</p>
                            )}
                            <small className="text-muted">
                              <strong>Cases ({f.case_count}):</strong> {f.case_numbers}
                            </small>
                          </Accordion.Body>
                        </Accordion.Item>
                      ))}
                    </Accordion>
                  </Card.Body>
                </Card>
              )}

              {outageResult.clusters && outageResult.clusters.length > 0 && (
                <Card className="mb-3">
                  <Card.Body>
                    <Card.Title>Clusters</Card.Title>
                    {outageResult.clusters.map((c) => (
                      <Card key={c.cluster_id} className="mb-2">
                        <Card.Body>
                          <Badge bg="info" className="me-2">Cluster {c.cluster_id}</Badge>
                          <Badge bg="info" className="me-2">{c.sr_count} SRs</Badge>
                          <strong>{c.topic}</strong>
                          <p className="mt-2" style={{ whiteSpace: 'pre-wrap' }}>{c.summary}</p>
                          {c.representative_sr_ids.length > 0 && (
                            <small className="text-muted">IDs: {c.representative_sr_ids.join(', ')}</small>
                          )}
                        </Card.Body>
                      </Card>
                    ))}
                  </Card.Body>
                </Card>
              )}
            </div>
          )}
        </Tab>

        <Tab eventKey="product" title="Forerunner L1 Summary">
          <Form onSubmit={handleProduct}>
            <Row className="g-3">
              <Col md={6}>
                <ProductNameCombobox value={productName} onChange={setProductName} required />
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Support Topic (optional)</Form.Label>
                  <Form.Control value={supportTopic} onChange={(e) => setSupportTopic(e.target.value)} />
                </Form.Group>
              </Col>
              <Col md={12}>
                <TimeRangeFilter
                  label="Product"
                  startDate={prodStartDate}
                  endDate={prodEndDate}
                  onChange={({ startDate, endDate }) => { setProdStartDate(startDate); setProdEndDate(endDate); }}
                  required
                />
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Support Case Severity Slice</Form.Label>
                  <Form.Select value={alertType} onChange={(e) => setAlertType(e.target.value)}>
                    <option value="Allsev">All technical support cases</option>
                    <option value="seva">Sev A cases only</option>
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label>Max SRs</Form.Label>
                  <Form.Control type="number" min={1} max={5000} value={prodMaxSrs} onChange={(e) => setProdMaxSrs(Number(e.target.value))} />
                </Form.Group>
              </Col>
            </Row>
            <div className="mt-3 d-flex gap-2 flex-wrap">
              <Button type="submit" disabled={loading}>
                {loading ? <><Spinner animation="border" size="sm" className="me-2" />Processing...</> : 'Summarize Product'}
              </Button>
              <Button variant="outline-secondary" size="sm" onClick={handleProductKqlPreview} disabled={productKqlPreviewLoading}>
                {productKqlPreviewLoading ? <Spinner animation="border" size="sm" /> : <><i className="bi bi-code-slash me-1" />Preview KQL Query</>}
              </Button>
            </div>
          </Form>

          {/* Product KQL Preview */}
          {productKqlPreview && (
            <Card className="mt-3 border-secondary">
              <Card.Header className="d-flex justify-content-between align-items-center bg-dark text-light">
                <span><i className="bi bi-code-slash me-2" />KQL Query Preview</span>
                <Button variant="outline-light" size="sm" onClick={() => copyToClipboard(productKqlPreview.query, 'KQL Query')}>
                  <i className="bi bi-clipboard me-1" />Copy
                </Button>
              </Card.Header>
              <Card.Body>
                <small className="text-muted d-block mb-2">
                  Cluster: <code>{productKqlPreview.cluster}</code> &mdash; Database: <code>{productKqlPreview.database}</code>
                </small>
                <pre className="bg-light p-3 rounded" style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', maxHeight: 400, overflow: 'auto' }}>
                  {productKqlPreview.query}
                </pre>
              </Card.Body>
            </Card>
          )}

          {productResult && (
            <div className="mt-4">
              {/* ---- Results header card ---- */}
              <Card className="mb-3 border-primary">
                <Card.Header className="bg-primary text-white d-flex align-items-center">
                  <i className="bi bi-bar-chart-line me-2" />
                  <strong>Product Summarization Results</strong>
                </Card.Header>
                <Card.Body>
                  <Row>
                    <Col md={6}>
                      <div className="mb-1"><strong>Product:</strong> {productResult.product_name}</div>
                      {productResult.support_topic && (
                        <div className="mb-1"><strong>Support Topic:</strong> {productResult.support_topic}</div>
                      )}
                    </Col>
                    <Col md={6}>
                      <div className="mb-1"><strong>Total SRs Processed:</strong> {productResult.total_srs_processed}</div>
                      <div className="mb-1"><strong>Support Area Groups:</strong> {productResult.topic_summaries.length}</div>
                    </Col>
                  </Row>
                  <hr className="my-2" />
                  <small className="text-muted">
                    Service requests are grouped by <strong>Support Area Path</strong>. Each section below contains an
                    AI-generated summary of the issue descriptions within that support area, along with the associated case numbers.
                  </small>
                </Card.Body>
              </Card>

              {productResult.topic_summaries.length === 0 && (
                <Alert variant="info">No topic summaries were generated for this query.</Alert>
              )}

              {productResult.topic_summaries.length > 0 && (
                <>
                  <div className="d-flex align-items-center mb-2">
                    <strong className="me-2">Summaries by Support Area Path</strong>
                    <Badge bg="secondary">{productResult.topic_summaries.length} groups</Badge>
                  </div>
                  <Accordion>
                    {productResult.topic_summaries.map((s, i) => (
                      <Accordion.Item eventKey={String(i)} key={i}>
                        <Accordion.Header>
                          <span className="me-auto" style={{ fontWeight: 500 }}>
                            <i className="bi bi-folder2-open me-1 text-primary" />
                            {s.topic || `Support Area ${i + 1}`}
                          </span>
                          <Badge bg="primary" className="ms-2">{s.sr_count} SR{s.sr_count !== 1 ? 's' : ''}</Badge>
                        </Accordion.Header>
                        <Accordion.Body>
                          <div className="mb-2">
                            <Badge bg="light" text="dark" className="me-1"><i className="bi bi-tag me-1" />Support Area Path</Badge>
                            <small className="text-muted">{s.topic}</small>
                          </div>
                          <Card className="mb-2 bg-light border-0">
                            <Card.Body className="py-2 px-3">
                              <small className="text-uppercase text-muted fw-bold d-block mb-1">AI Summary</small>
                              <p className="mb-0" style={{ whiteSpace: 'pre-wrap' }}>{s.summary}</p>
                            </Card.Body>
                          </Card>
                          {s.cases && s.cases.length > 0 && (
                            <div className="mt-2">
                              <small className="text-uppercase text-muted fw-bold d-block mb-1">Case Numbers ({s.cases.length})</small>
                              <small className="text-muted">{s.cases.slice(0, 30).join(', ')}{s.cases.length > 30 ? ` … and ${s.cases.length - 30} more` : ''}</small>
                            </div>
                          )}
                        </Accordion.Body>
                      </Accordion.Item>
                    ))}
                  </Accordion>
                </>
              )}
            </div>
          )}
        </Tab>
      </Tabs>
    </Container>
  );
}
