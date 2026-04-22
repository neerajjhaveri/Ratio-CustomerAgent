/** Request / response types for the SR Insights API. */

export interface OutageSummarizeRequest {
  outage_id?: number;
  start_date?: string;
  end_date?: string;
  service_name?: string;
  max_srs: number;
  include_faq: boolean;
  include_executive_summary: boolean;
  include_clusters: boolean;
}

export interface FaqItem {
  question: string;
  answer?: string;
  case_count: string;
  case_numbers: string;
}

export interface ClusterSummary {
  cluster_id: number;
  topic: string;
  sr_count: number;
  summary: string;
  representative_sr_ids: string[];
}

export interface OutageSummarizeResponse {
  outage_id?: number;
  total_srs_processed: number;
  executive_summary?: string;
  faq?: FaqItem[];
  clusters?: ClusterSummary[];
  timestamp: string;
}

export interface ProductSummarizeRequest {
  product_name: string;
  support_topic?: string;
  start_date: string;
  end_date: string;
  alert_type: string;
  max_srs: number;
}

export interface TopicSummary {
  topic: string;
  sr_count: number;
  summary: string;
  cases: string[];
  start_time?: string;
  end_time?: string;
}

export interface ProductSummarizeResponse {
  product_name: string;
  support_topic?: string;
  total_srs_processed: number;
  topic_summaries: TopicSummary[];
  timestamp: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

/* ---------- Preview types ---------- */

export interface QueryPreviewResponse {
  query: string;
  database: string;
  cluster: string;
}

export interface PromptStage {
  stage_name: string;
  description: string;
  system_message: string;
  user_message: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface OutagePromptsPreviewResponse {
  stages: PromptStage[];
  sr_count: number;
  note: string;
}

export interface ProductNamesResponse {
  names: string[];
  count: number;
}
