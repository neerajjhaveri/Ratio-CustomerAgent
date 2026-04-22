/**
 * ThinkingStepper — visual progress stepper for the Fuse thinking model.
 *
 * Steps light up based on evaluation progress (scenario selected → loading → results → recommendations).
 */
import { THINKING_STEPS } from '../../constants/fuse';

interface ThinkingStepperProps {
  /** Number of the highest completed step (0 = none). */
  currentStep: number;
}

export default function ThinkingStepper({ currentStep }: ThinkingStepperProps) {
  return (
    <div
      className="d-flex align-items-center gap-1 mb-3 px-3 py-2 rounded"
      style={{ background: '#f0f4ff', border: '1px solid #dbeafe', fontSize: '0.78rem', flexWrap: 'wrap' }}
    >
      {THINKING_STEPS.map((step, i) => {
        const isActive = currentStep >= step.num;
        return (
          <span key={step.num} className="d-flex align-items-center">
            <span
              className="d-inline-flex align-items-center justify-content-center rounded-circle me-1"
              style={{
                width: 22, height: 22, fontSize: '0.7rem', fontWeight: 700,
                background: isActive ? step.color : '#e5e7eb',
                color: isActive ? '#fff' : '#9ca3af',
              }}
            >
              {step.num}
            </span>
            <span style={{ color: isActive ? step.color : '#9ca3af', fontWeight: isActive ? 600 : 400 }}>
              {step.label}
            </span>
            {i < THINKING_STEPS.length - 1 && (
              <i className="bi bi-chevron-right text-muted mx-1" style={{ fontSize: '0.65rem' }} />
            )}
          </span>
        );
      })}
    </div>
  );
}
