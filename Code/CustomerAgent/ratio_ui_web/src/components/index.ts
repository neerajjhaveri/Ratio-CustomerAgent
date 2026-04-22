/**
 * Reusable UI components.
 *
 * Organisation:
 *   components/layout/   — shell, nav, sidebar
 *   components/common/   — shared widgets (filters, comboboxes)
 *   components/fuse/     — Fuse Studio evaluation components
 *
 * Re-export public components from this barrel:
 *   import { Sidebar, MetricsTable } from '../components';
 */

// Layout
export { default as Sidebar } from './layout/Sidebar';

// Common / shared
export { default as ProductNameCombobox } from './common/ProductNameCombobox';
export { default as TimeRangeFilter } from './common/TimeRangeFilter';
export type { TimeRange } from './common/TimeRangeFilter';

// Fuse Studio
export { default as DiagnosticsPanel } from './fuse/DiagnosticsPanel';
export { default as FusePipelineProgress } from './fuse/FusePipelineProgress';
export type { FusePipelineProgressProps, PipelineStepStatus } from './fuse/FusePipelineProgress';
export { default as MetricsTable } from './fuse/MetricsTable';
export { default as RecommendationsPanel } from './fuse/RecommendationsPanel';
export { default as ResultsSummary } from './fuse/ResultsSummary';
export { default as SafetyPromptPanel } from './fuse/SafetyPromptPanel';
export { default as ThinkingStepper } from './fuse/ThinkingStepper';
