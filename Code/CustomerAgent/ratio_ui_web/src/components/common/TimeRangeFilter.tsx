import { useState } from 'react';
import Form from 'react-bootstrap/Form';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import InputGroup from 'react-bootstrap/InputGroup';

/* ------------------------------------------------------------------ */
/* Preset quick-select options                                         */
/* ------------------------------------------------------------------ */
const PRESETS = [
  { label: 'Last 15 minutes', minutes: 15 },
  { label: 'Last 30 minutes', minutes: 30 },
  { label: 'Last 1 hour', minutes: 60 },
  { label: 'Last 3 hours', minutes: 180 },
  { label: 'Last 6 hours', minutes: 360 },
  { label: 'Last 12 hours', minutes: 720 },
  { label: 'Last 24 hours', minutes: 1440 },
  { label: 'Last 2 days', minutes: 2880 },
  { label: 'Last 5 days', minutes: 7200 },
  { label: 'Last 7 days', minutes: 10080 },
  { label: 'Last 10 days', minutes: 14400 },
  { label: 'Last 20 days', minutes: 28800 },
  { label: 'Last 30 days', minutes: 43200 },
] as const;

type Mode = 'preset' | 'custom';

export interface TimeRange {
  startDate: string;  // ISO 8601 datetime string
  endDate: string;    // ISO 8601 datetime string
}

interface Props {
  /** Current start value (ISO string or empty) */
  startDate: string;
  /** Current end value (ISO string or empty) */
  endDate: string;
  /** Called whenever the resolved start/end changes */
  onChange: (range: TimeRange) => void;
  /** Mark the fields as required in the form */
  required?: boolean;
  /** Label prefix, e.g. "Start Date" / "End Date" */
  label?: string;
  /** Show as disabled / placeholder when not yet connected */
  disabled?: boolean;
}

/** Pad a number to 2 digits. */
const pad = (n: number) => String(n).padStart(2, '0');

/** Format a Date as a `datetime-local` input value. */
function toLocalInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Apply a preset: end = now, start = now − minutes. */
function applyPreset(minutes: number): TimeRange {
  const now = new Date();
  const start = new Date(now.getTime() - minutes * 60_000);
  return { startDate: start.toISOString(), endDate: now.toISOString() };
}

export default function TimeRangeFilter({
  startDate,
  endDate,
  onChange,
  required = false,
  label = '',
  disabled = false,
}: Props) {
  const [mode, setMode] = useState<Mode>('preset');
  const [selectedPreset, setSelectedPreset] = useState('');

  /* ---- custom fields (datetime-local values) ---- */
  const [customStart, setCustomStart] = useState(startDate ? toLocalInput(new Date(startDate)) : '');
  const [customEnd, setCustomEnd] = useState(endDate ? toLocalInput(new Date(endDate)) : '');

  const handleModeChange = (newMode: Mode) => {
    setMode(newMode);
    if (newMode === 'preset' && selectedPreset) {
      onChange(applyPreset(Number(selectedPreset)));
    } else if (newMode === 'custom' && customStart && customEnd) {
      onChange({ startDate: new Date(customStart).toISOString(), endDate: new Date(customEnd).toISOString() });
    }
  };

  const handlePresetChange = (value: string) => {
    setSelectedPreset(value);
    if (value) {
      onChange(applyPreset(Number(value)));
    }
  };

  const handleCustomStart = (value: string) => {
    setCustomStart(value);
    if (value && customEnd) {
      onChange({ startDate: new Date(value).toISOString(), endDate: new Date(customEnd).toISOString() });
    }
  };

  const handleCustomEnd = (value: string) => {
    setCustomEnd(value);
    if (customStart && value) {
      onChange({ startDate: new Date(customStart).toISOString(), endDate: new Date(value).toISOString() });
    }
  };

  const labelPrefix = label ? `${label} — ` : '';

  return (
    <div className={disabled ? 'opacity-50' : ''}>
      <Form.Label className="fw-semibold">
        {labelPrefix}Time Range {!required && <small className="text-muted">(optional)</small>}
      </Form.Label>

      {/* Mode toggle */}
      <div className="mb-2">
        <Form.Check
          inline
          type="radio"
          id={`${label}-mode-preset`}
          label="Quick select"
          checked={mode === 'preset'}
          onChange={() => handleModeChange('preset')}
          disabled={disabled}
        />
        <Form.Check
          inline
          type="radio"
          id={`${label}-mode-custom`}
          label="Custom range"
          checked={mode === 'custom'}
          onChange={() => handleModeChange('custom')}
          disabled={disabled}
        />
      </div>

      {mode === 'preset' ? (
        <Form.Select
          value={selectedPreset}
          onChange={(e) => handlePresetChange(e.target.value)}
          disabled={disabled}
        >
          <option value="">— Select time range —</option>
          {PRESETS.map((p) => (
            <option key={p.minutes} value={p.minutes}>
              {p.label}
            </option>
          ))}
        </Form.Select>
      ) : (
        <Row className="g-2">
          <Col>
            <InputGroup size="sm">
              <InputGroup.Text>From</InputGroup.Text>
              <Form.Control
                type="datetime-local"
                value={customStart}
                onChange={(e) => handleCustomStart(e.target.value)}
                disabled={disabled}
              />
            </InputGroup>
          </Col>
          <Col>
            <InputGroup size="sm">
              <InputGroup.Text>To</InputGroup.Text>
              <Form.Control
                type="datetime-local"
                value={customEnd}
                onChange={(e) => handleCustomEnd(e.target.value)}
                disabled={disabled}
              />
            </InputGroup>
          </Col>
        </Row>
      )}
    </div>
  );
}
