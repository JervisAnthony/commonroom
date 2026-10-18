/** In-memory simulation only. These values are never consent or authorization. */
export const EXAMPLE_CONTACTS = [
  { id: 'example-lantern', label: 'Example Lantern', initial: 'L' },
  { id: 'example-fern', label: 'Example Fern', initial: 'F' },
] as const;

export const PREVIEW_SCOPES = ['PRESENCE', 'APPROXIMATE', 'PRECISE'] as const;
export const PREVIEW_DURATIONS = [
  { seconds: 60, label: '1 minute' },
  { seconds: 900, label: '15 minutes' },
  { seconds: 3600, label: '1 hour' },
  { seconds: 86400, label: '24 hours' },
] as const;

export type ExampleRecipient = (typeof EXAMPLE_CONTACTS)[number]['id'];
export type PreviewScope = (typeof PREVIEW_SCOPES)[number];
export type PreviewSelection = Readonly<{
  recipientId: ExampleRecipient;
  direction: 'outgoing';
  scope: PreviewScope;
  durationSeconds: number;
}>;
export type PreviewSession = PreviewSelection & Readonly<{
  runNumber: number;
  startedAtMs: number;
  expiresAtMs: number;
}>;
export type PreviewState =
  | Readonly<{ phase: 'idle'; runNumber: 0 }>
  | Readonly<{ phase: 'running'; runNumber: number; session: PreviewSession }>
  | Readonly<{ phase: 'cancelled' | 'expired'; runNumber: number; session: PreviewSession; endedAtMs: number }>;

function requireTime(nowMs: number): void {
  if (!Number.isSafeInteger(nowMs) || nowMs < 0) {
    throw new RangeError('Preview time must be a nonnegative integer in milliseconds.');
  }
}

export function createPreviewState(): PreviewState {
  return Object.freeze({ phase: 'idle', runNumber: 0 });
}

/** Terminal states stay terminal, even if a later clock reading moves backwards. */
export function advancePreview(state: PreviewState, nowMs: number): PreviewState {
  requireTime(nowMs);
  if (state.phase !== 'running' || nowMs < state.session.expiresAtMs) return state;
  return Object.freeze({ ...state, phase: 'expired', endedAtMs: state.session.expiresAtMs });
}

/** The only activation path. Every call represents another explicit user action. */
export function beginPreview(state: PreviewState, selection: PreviewSelection, nowMs: number): PreviewState {
  requireTime(nowMs);
  if (!selection || !EXAMPLE_CONTACTS.some(contact => contact.id === selection.recipientId)) {
    throw new RangeError('Choose a fictional example recipient.');
  }
  if (selection.direction !== 'outgoing' || !PREVIEW_SCOPES.includes(selection.scope)) {
    throw new RangeError('Choose an outgoing preview and a supported scope.');
  }
  if (!Number.isSafeInteger(selection.durationSeconds) || selection.durationSeconds < 60 || selection.durationSeconds > 86400) {
    throw new RangeError('Choose a duration from 60 to 86400 seconds, inclusive.');
  }
  const expiresAtMs = nowMs + selection.durationSeconds * 1000;
  if (!Number.isSafeInteger(expiresAtMs)) throw new RangeError('Preview expiry exceeds the supported clock range.');
  if (advancePreview(state, nowMs).phase === 'running') {
    throw new Error('End the current simulated preview before starting another.');
  }
  const runNumber = state.runNumber + 1;
  // Project the supported fields; never retain arbitrary input properties or references.
  const session = Object.freeze({
    recipientId: selection.recipientId, direction: selection.direction,
    scope: selection.scope, durationSeconds: selection.durationSeconds,
    runNumber, startedAtMs: nowMs, expiresAtMs,
  });
  return Object.freeze({ phase: 'running', runNumber, session });
}

export function endPreview(state: PreviewState, nowMs: number): PreviewState {
  const current = advancePreview(state, nowMs);
  if (current.phase !== 'running') return current;
  // Clock rollback must not put cancellation before the start; cancellation is still immediate.
  return Object.freeze({ ...current, phase: 'cancelled', endedAtMs: Math.max(nowMs, current.session.startedAtMs) });
}
