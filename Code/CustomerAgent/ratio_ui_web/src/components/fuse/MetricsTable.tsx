/**
 * MetricsTable — displays the decision-aware metric results in a responsive table.
 */
import Badge from 'react-bootstrap/Badge';
import Card from 'react-bootstrap/Card';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Table from 'react-bootstrap/Table';
import type { MetricResult } from '../../types/fuse';
import { STATUS_BG, STATUS_COLORS } from '../../constants/fuse';

function formatMetricValue(metric: MetricResult): string {
  if (metric.unit === 'ratio') return `${(metric.value * 100).toFixed(1)}%`;
  if (metric.unit === 'score') return metric.value.toFixed(2);
  return String(metric.value);
}

function metricProgressVariant(status: string): string {
  if (status === 'good') return 'success';
  if (status === 'warning') return 'warning';
  if (status === 'bad') return 'danger';
  return 'secondary';
}

function MetricProgressBar({ metric }: { metric: MetricResult }) {
  if (metric.unit !== 'ratio') return null;
  const pct = Math.min(metric.value * 100, 100);
  return <ProgressBar now={pct} variant={metricProgressVariant(metric.status)} style={{ height: 6, borderRadius: 3 }} />;
}

interface MetricsTableProps {
  metrics: MetricResult[];
}

export default function MetricsTable({ metrics }: MetricsTableProps) {
  return (
    <Card className="mb-4 border-0 shadow-sm">
      <Card.Header className="bg-white border-bottom">
        <div className="d-flex align-items-center">
          <span
            className="d-inline-flex align-items-center justify-content-center rounded-circle me-2"
            style={{ width: 24, height: 24, background: '#ca8a04', color: '#fff', fontSize: '0.75rem', fontWeight: 700 }}
          >
            3
          </span>
          <strong>Decision-Aware Metrics</strong>
          <small className="text-muted ms-2">— Failure modes detected and scored across your cases</small>
        </div>
      </Card.Header>
      <Card.Body className="p-0">
        <Table hover responsive className="mb-0">
          <thead>
            <tr style={{ fontSize: '0.82rem' }}>
              <th style={{ width: '30%' }}>Metric</th>
              <th style={{ width: '20%' }}>Value</th>
              <th style={{ width: '15%' }}>Target</th>
              <th style={{ width: '10%' }}>Status</th>
              <th style={{ width: '25%' }}>Breakdown</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={metric.metric_id}>
                <td>
                  <strong style={{ fontSize: '0.85rem' }}>{metric.display_name}</strong>
                </td>
                <td>
                  <span className="fw-bold" style={{ fontSize: '1rem', color: STATUS_COLORS[metric.status] || '#6b7280' }}>
                    {formatMetricValue(metric)}
                  </span>
                  <MetricProgressBar metric={metric} />
                </td>
                <td className="text-muted" style={{ fontSize: '0.85rem' }}>
                  {metric.target != null
                    ? metric.unit === 'ratio'
                      ? `${(metric.target * 100).toFixed(0)}%`
                      : metric.target
                    : '—'}
                </td>
                <td>
                  <Badge bg={STATUS_BG[metric.status] || 'secondary'}>
                    {metric.status === 'good' && <i className="bi bi-check-circle me-1" />}
                    {metric.status === 'warning' && <i className="bi bi-exclamation-triangle me-1" />}
                    {metric.status === 'bad' && <i className="bi bi-x-circle me-1" />}
                    {metric.status}
                  </Badge>
                </td>
                <td className="text-muted" style={{ fontSize: '0.82rem' }}>
                  {metric.numerator != null && metric.denominator != null ? `${metric.numerator} / ${metric.denominator}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card.Body>
    </Card>
  );
}
