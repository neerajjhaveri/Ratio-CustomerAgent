/**
 * Shared TypeScript types for the Ratio AI frontend.
 *
 * Organise domain types into separate files as the app grows:
 *   types/api.ts       — request / response shapes
 *   types/models.ts    — domain entities
 *   types/common.ts    — shared utility types
 *
 * Re-export everything from this barrel so consumers import from "types":
 *   import type { ApiError } from '../types';
 */

/** Standard error shape returned by the backend. */
export interface ApiError {
  detail: string;
  status?: number;
}
