/**
 * SafetyPromptPanel — optional AI safety red-team prompt generator.
 */
import { useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Badge from 'react-bootstrap/Badge';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Form from 'react-bootstrap/Form';
import Row from 'react-bootstrap/Row';
import Spinner from 'react-bootstrap/Spinner';
import { generateSafetyPrompts } from '../../api/fuseClient';
import type { GeneratedPrompt, SafetyOption, SafetyOptionsResponse } from '../../types/fuse';

interface SafetyPromptPanelProps {
  /** Available options from the safety service, or null if unavailable. */
  safetyOptions: SafetyOptionsResponse | null;
  /** Error message when the safety service is unreachable. */
  safetyError: string | null;
  /** Callback to propagate errors to the parent page. */
  onError: (msg: string) => void;
}

export default function SafetyPromptPanel({ safetyOptions, safetyError, onError }: SafetyPromptPanelProps) {
  const [selectedCategories, setSelectedCategories] = useState<string[]>(
    () => safetyOptions?.risk_categories.slice(0, 2).map((c: SafetyOption) => c.name) ?? [],
  );
  const [generatedPrompts, setGeneratedPrompts] = useState<GeneratedPrompt[]>([]);
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    onError('');
    setLoading(true);
    try {
      const response = await generateSafetyPrompts({
        risk_categories: selectedCategories,
        num_prompts_per_category: 5,
      });
      setGeneratedPrompts(response.prompts);
    } catch (err) {
      onError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="mt-4 border-0 shadow-sm">
      <Card.Header className="bg-white border-bottom">
        <div className="d-flex align-items-center">
          <i className="bi bi-shield-exclamation me-2" style={{ color: '#dc2626' }} />
          <strong>AI Safety Prompt Generator</strong>
          <Badge bg="light" text="muted" className="ms-2" style={{ fontSize: '0.7rem' }}>
            Optional
          </Badge>
        </div>
      </Card.Header>
      <Card.Body>
        {safetyError ? (
          <Alert variant="warning" className="mb-0">
            <i className="bi bi-exclamation-triangle me-2" />
            {safetyError}
          </Alert>
        ) : (
          <>
            <Row className="g-3 align-items-end">
              <Col md={8}>
                <Form.Group>
                  <Form.Label className="fw-semibold">Risk Categories</Form.Label>
                  <div className="d-flex flex-wrap gap-2">
                    {(safetyOptions?.risk_categories ?? []).map((category) => {
                      const selected = selectedCategories.includes(category.name);
                      return (
                        <Button
                          key={category.name}
                          size="sm"
                          variant={selected ? 'primary' : 'outline-secondary'}
                          title={category.description}
                          onClick={() =>
                            setSelectedCategories((prev) =>
                              prev.includes(category.name)
                                ? prev.filter((c) => c !== category.name)
                                : [...prev, category.name],
                            )
                          }
                        >
                          {selected && <i className="bi bi-check2 me-1" />}
                          {category.name}
                        </Button>
                      );
                    })}
                  </div>
                </Form.Group>
              </Col>
              <Col md={4}>
                <Button onClick={handleGenerate} disabled={loading || selectedCategories.length === 0} className="w-100">
                  {loading ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-2" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-lightning-charge me-1" />
                      Generate Prompts
                    </>
                  )}
                </Button>
              </Col>
            </Row>

            {generatedPrompts.length > 0 && (
              <div className="mt-3">
                <h6>
                  <i className="bi bi-chat-dots me-1" />
                  Generated Prompts ({generatedPrompts.length})
                </h6>
                <div style={{ maxHeight: 300, overflow: 'auto' }}>
                  {generatedPrompts.map((prompt) => (
                    <Card key={`${prompt.category}-${prompt.id}`} className="mb-2">
                      <Card.Body className="py-2 px-3">
                        <Badge bg="secondary" className="mb-1" style={{ fontSize: '0.7rem' }}>
                          {prompt.category}
                        </Badge>
                        <div style={{ fontSize: '0.85rem' }}>{prompt.prompt}</div>
                      </Card.Body>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
}
