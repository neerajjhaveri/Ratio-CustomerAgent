/**
 * Shared constants for the Fuse Studio UI — status colours, default data.
 */
import type { ScenarioCaseInput } from '../types/fuse';

/** Colour mapping for metric status badges and values. */
export const STATUS_COLORS: Record<string, string> = {
  good: '#16a34a',
  warning: '#ca8a04',
  bad: '#dc2626',
  unknown: '#6b7280',
};

/** Bootstrap variant mapping for status badges. */
export const STATUS_BG: Record<string, string> = {
  good: 'success',
  warning: 'warning',
  bad: 'danger',
  unknown: 'secondary',
};

/** The Fuse thinking-model steps shown in the stepper. */
export const THINKING_STEPS = [
  { num: 1, label: 'Business Goal', icon: 'bi-bullseye', desc: 'What outcome matters?', color: '#2563eb' },
  { num: 2, label: 'Agent Decision', icon: 'bi-signpost-split', desc: 'What did the agent decide?', color: '#7c3aed' },
  { num: 3, label: 'Failure Mode', icon: 'bi-exclamation-triangle', desc: 'What could go wrong?', color: '#dc2626' },
  { num: 4, label: 'Observable Signals', icon: 'bi-broadcast', desc: 'What data did we capture?', color: '#ea580c' },
  { num: 5, label: 'Metric', icon: 'bi-speedometer2', desc: 'How are we scoring it?', color: '#ca8a04' },
  { num: 6, label: 'Improvement Action', icon: 'bi-wrench-adjustable', desc: 'What should we fix?', color: '#16a34a' },
] as const;

/** Pre-filled sample case for the JSON editor. */
export const DEFAULT_CASE: ScenarioCaseInput = {
  case_id: 'sample-1',
  query: 'Customer asks to increase token count limit for subscription.',
  answer: 'Please provide your subscription ID and region and we will review the quota increase.',
  signals: {
    final_action: 'sent',
    support_agent_verdict: 'reject',
    send_justified: false,
    escalation_needed: true,
    escalated: false,
    clarification_needed: true,
    clarification_asked: false,
    routing_correct: true,
    fallback_used: false,
    fallback_was_necessary: false,
    engineer_rewrite_required: true,
  },
  metadata: {
    topic: 'quota',
    product: 'azure-openai',
  },
};
