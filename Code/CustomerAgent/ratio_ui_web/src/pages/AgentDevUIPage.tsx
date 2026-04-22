import { useState, useEffect, useRef, type FormEvent } from 'react';
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Badge from 'react-bootstrap/Badge';
import Alert from 'react-bootstrap/Alert';
import Spinner from 'react-bootstrap/Spinner';
import ListGroup from 'react-bootstrap/ListGroup';
import {
  listAFAgents,
  getAFConfig,
  chatWithAgent,
  type AFAgentInfo,
  type AFConfigResponse,
} from '../api/agentFrameworkClient';

interface ChatMessage {
  role: 'user' | 'assistant';
  agent?: string;
  text: string;
  timestamp: Date;
}

export default function AgentDevUIPage() {
  const [config, setConfig] = useState<AFConfigResponse | null>(null);
  const [agents, setAgents] = useState<AFAgentInfo[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('Generic_Agent');
  const [sessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initLoading, setInitLoading] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load config & agents on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cfgResult, agentsResult] = await Promise.all([
          getAFConfig().catch(() => null),
          listAFAgents().catch(() => ({ agents: [] })),
        ]);
        if (cancelled) return;
        if (cfgResult) setConfig(cfgResult);
        setAgents(agentsResult.agents);
        if (agentsResult.agents.length > 0 && !agentsResult.agents.find(a => a.name === selectedAgent)) {
          setSelectedAgent(agentsResult.agents[0].name);
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      } finally {
        if (!cancelled) setInitLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setInput('');
    setError(null);

    const userMsg: ChatMessage = { role: 'user', text, timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const result = await chatWithAgent({
        agent_name: selectedAgent,
        message: text,
        session_id: sessionId,
      });
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        agent: result.agent,
        text: result.response,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    setError(null);
  };

  const currentAgentInfo = agents.find(a => a.name === selectedAgent);

  if (initLoading) {
    return (
      <Container className="py-4 text-center">
        <Spinner animation="border" /> <span className="ms-2">Loading Agent Framework...</span>
      </Container>
    );
  }

  return (
    <Container fluid className="py-3 px-4" style={{ maxHeight: '100vh', overflow: 'hidden' }}>
      {/* Page header */}
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <h4 className="mb-0">
            <i className="bi bi-robot me-2" />
            Agent DevUI
          </h4>
          <small className="text-muted">
            Interactive testing for Microsoft Agent Framework agents
          </small>
        </div>
        <div className="d-flex align-items-center gap-2">
          {config && (
            <Badge bg={config.agent_framework_available ? 'success' : 'secondary'}>
              Agent Framework {config.agent_framework_available ? 'Available' : 'Unavailable'}
            </Badge>
          )}
          <Badge bg="info">Provider: {config?.provider ?? 'unknown'}</Badge>
          <Badge bg="outline-secondary" text="dark" className="border">
            Session: {sessionId.slice(0, 8)}...
          </Badge>
        </div>
      </div>

      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Row style={{ height: 'calc(100vh - 140px)' }}>
        {/* Left panel — Agent directory */}
        <Col md={3} className="h-100 overflow-auto">
          <Card className="h-100 shadow-sm">
            <Card.Header className="fw-semibold">
              <i className="bi bi-collection me-2" />
              Agent Directory
            </Card.Header>
            <ListGroup variant="flush">
              {agents.map(agent => (
                <ListGroup.Item
                  key={agent.name}
                  action
                  active={agent.name === selectedAgent}
                  onClick={() => setSelectedAgent(agent.name)}
                  className="d-flex flex-column"
                >
                  <div className="d-flex justify-content-between align-items-center">
                    <strong style={{ fontSize: '0.9rem' }}>{agent.name.replace(/_/g, ' ')}</strong>
                    {agent.tools.length > 0 && (
                      <Badge bg="warning" text="dark" pill>
                        {agent.tools.length} tool{agent.tools.length > 1 ? 's' : ''}
                      </Badge>
                    )}
                  </div>
                  <small
                    className={agent.name === selectedAgent ? 'text-white-50' : 'text-muted'}
                    style={{ fontSize: '0.75rem', lineHeight: 1.3, marginTop: 4 }}
                  >
                    {agent.instructions.slice(0, 80)}...
                  </small>
                </ListGroup.Item>
              ))}
            </ListGroup>
          </Card>
        </Col>

        {/* Center panel — Chat */}
        <Col md={6} className="h-100 d-flex flex-column">
          <Card className="flex-grow-1 shadow-sm d-flex flex-column" style={{ overflow: 'hidden' }}>
            <Card.Header className="d-flex justify-content-between align-items-center">
              <span className="fw-semibold">
                <i className="bi bi-chat-dots me-2" />
                Chat — {selectedAgent.replace(/_/g, ' ')}
              </span>
              <Button variant="outline-secondary" size="sm" onClick={handleClear}>
                <i className="bi bi-trash me-1" />Clear
              </Button>
            </Card.Header>

            {/* Messages */}
            <Card.Body className="flex-grow-1 overflow-auto p-3" style={{ background: '#f8f9fa' }}>
              {messages.length === 0 && (
                <div className="text-center text-muted mt-5">
                  <i className="bi bi-chat-left-text" style={{ fontSize: 48, opacity: 0.3 }} />
                  <p className="mt-2">Send a message to start chatting with the agent.</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`d-flex mb-3 ${msg.role === 'user' ? 'justify-content-end' : 'justify-content-start'}`}
                >
                  <div
                    style={{
                      maxWidth: '80%',
                      padding: '10px 14px',
                      borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                      background: msg.role === 'user' ? '#1e3c72' : '#fff',
                      color: msg.role === 'user' ? '#fff' : '#333',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                      fontSize: '0.9rem',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {msg.role === 'assistant' && msg.agent && (
                      <div style={{ fontSize: '0.7rem', color: '#6c757d', marginBottom: 4 }}>
                        {msg.agent.replace(/_/g, ' ')}
                      </div>
                    )}
                    {msg.text}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="d-flex justify-content-start mb-3">
                  <div style={{ padding: '10px 14px', borderRadius: '16px 16px 16px 4px', background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <Spinner animation="grow" size="sm" className="me-1" />
                    <Spinner animation="grow" size="sm" className="me-1" style={{ animationDelay: '0.15s' }} />
                    <Spinner animation="grow" size="sm" style={{ animationDelay: '0.3s' }} />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </Card.Body>

            {/* Input */}
            <Card.Footer className="p-2">
              <Form onSubmit={handleSend} className="d-flex gap-2">
                <Form.Control
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder={`Message ${selectedAgent.replace(/_/g, ' ')}...`}
                  disabled={loading}
                  autoFocus
                />
                <Button type="submit" disabled={loading || !input.trim()}>
                  <i className="bi bi-send" />
                </Button>
              </Form>
            </Card.Footer>
          </Card>
        </Col>

        {/* Right panel — Agent details */}
        <Col md={3} className="h-100 overflow-auto">
          <Card className="shadow-sm mb-3">
            <Card.Header className="fw-semibold">
              <i className="bi bi-info-circle me-2" />
              Agent Details
            </Card.Header>
            <Card.Body style={{ fontSize: '0.85rem' }}>
              {currentAgentInfo ? (
                <>
                  <div className="mb-2">
                    <strong>Name:</strong> {currentAgentInfo.name}
                  </div>
                  <div className="mb-2">
                    <strong>Instructions:</strong>
                    <p className="text-muted mt-1 mb-0" style={{ fontSize: '0.8rem' }}>
                      {currentAgentInfo.instructions}
                    </p>
                  </div>
                  {currentAgentInfo.tools.length > 0 && (
                    <div>
                      <strong>Tools:</strong>
                      <div className="mt-1 d-flex flex-wrap gap-1">
                        {currentAgentInfo.tools.map(t => (
                          <Badge key={t} bg="secondary" className="fw-normal">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <span className="text-muted">Select an agent</span>
              )}
            </Card.Body>
          </Card>

          <Card className="shadow-sm">
            <Card.Header className="fw-semibold">
              <i className="bi bi-terminal me-2" />
              Session Info
            </Card.Header>
            <Card.Body style={{ fontSize: '0.8rem' }}>
              <div className="mb-1"><strong>Session ID:</strong></div>
              <code style={{ fontSize: '0.7rem', wordBreak: 'break-all' }}>{sessionId}</code>
              <div className="mt-2"><strong>Messages:</strong> {messages.length}</div>
              <div><strong>Provider:</strong> {config?.provider ?? '—'}</div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
}
