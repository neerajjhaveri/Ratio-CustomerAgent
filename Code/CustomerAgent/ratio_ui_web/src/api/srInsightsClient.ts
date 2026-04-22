/**
 * HTTP client for the SR Insights microservice.
 *
 * In development the Vite dev server proxies `/sr-api` → `http://127.0.0.1:8006`
 * (configured in vite.config.ts, with path rewrite stripping the prefix).
 */

import type {
  OutageSummarizeRequest,
  OutageSummarizeResponse,
  ProductSummarizeRequest,
  ProductSummarizeResponse,
  HealthResponse,
  QueryPreviewResponse,
  OutagePromptsPreviewResponse,
  ProductNamesResponse,
} from '../types/srInsights';

const SR_PREFIX = '/sr-api';

async function srFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${SR_PREFIX}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SR Insights ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return srFetch<HealthResponse>('/health');
}

export function summarizeOutage(body: OutageSummarizeRequest): Promise<OutageSummarizeResponse> {
  return srFetch<OutageSummarizeResponse>('/v1/summarize-outage', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function summarizeProduct(body: ProductSummarizeRequest): Promise<ProductSummarizeResponse> {
  return srFetch<ProductSummarizeResponse>('/v1/summarize-product', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function previewOutageQuery(outageId: number): Promise<QueryPreviewResponse> {
  return srFetch<QueryPreviewResponse>('/v1/preview/outage-query', {
    method: 'POST',
    body: JSON.stringify({ outage_id: outageId }),
  });
}

export function previewProductQuery(
  productName: string,
  startDate: string,
  endDate: string,
  alertType: string,
): Promise<QueryPreviewResponse> {
  return srFetch<QueryPreviewResponse>('/v1/preview/product-query', {
    method: 'POST',
    body: JSON.stringify({
      product_name: productName,
      start_date: startDate,
      end_date: endDate,
      alert_type: alertType,
    }),
  });
}

export function previewOutagePrompts(outageId: number): Promise<OutagePromptsPreviewResponse> {
  return srFetch<OutagePromptsPreviewResponse>('/v1/preview/outage-prompts', {
    method: 'POST',
    body: JSON.stringify({ outage_id: outageId }),
  });
}

export function getProductNames(): Promise<ProductNamesResponse> {
  return srFetch<ProductNamesResponse>('/v1/product-names');
}
