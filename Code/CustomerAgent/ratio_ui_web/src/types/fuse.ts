export interface ScenarioCaseInput {
  case_id: string;
  query?: string;
  answer?: string;
  references?: string[];
  ground_truth?: string;
  signals?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface EvaluateScenarioRequest {
  scenario_id: string;
  include_case_diagnostics?: boolean;
  cases: ScenarioCaseInput[];
}

export interface MetricResult {
  metric_id: string;
  display_name: string;
  value: number;
  unit: 'ratio' | 'count' | 'score';
  target?: number;
  status: 'good' | 'warning' | 'bad' | 'unknown';
  numerator?: number;
  denominator?: number;
}

export interface Recommendation {
  metric_id: string;
  priority: 'low' | 'medium' | 'high';
  message: string;
  suggested_actions: string[];
}

export interface CaseFailureMode {
  failure_mode_id: string;
  triggered: boolean;
}

export interface CaseDecisionResult {
  case_id: string;
  failure_modes: CaseFailureMode[];
  computed_signals: Record<string, unknown>;
  errors: string[];
}

export interface EvaluateScenarioResponse {
  scenario_id: string;
  scenario_name: string;
  case_count: number;
  metrics: MetricResult[];
  recommendations: Recommendation[];
  diagnostics?: CaseDecisionResult[];
}

export interface ScenarioSummary {
  scenario_id: string;
  name: string;
  description: string;
  supported_metrics: string[];
}

export interface ScenariosResponse {
  scenarios: ScenarioSummary[];
}

export interface SafetyOption {
  name: string;
  description: string;
}

export interface SafetyOptionsResponse {
  risk_categories: SafetyOption[];
  attack_strategies: SafetyOption[];
  default_attack_strategies?: string[];
  default_num_objectives?: number;
  max_num_objectives?: number;
}

export interface SafetyPromptRequest {
  risk_categories: string[];
  num_prompts_per_category: number;
}

export interface GeneratedPrompt {
  id: number;
  prompt: string;
  category: string;
}

export interface SafetyPromptResponse {
  prompts: GeneratedPrompt[];
  total_count: number;
  risk_categories: string[];
}

export interface MockModeResponse {
  mock_mode: boolean;
  changed?: boolean;
}
