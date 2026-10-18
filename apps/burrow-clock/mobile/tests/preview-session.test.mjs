import test from 'node:test';
import assert from 'node:assert/strict';
import {
  EXAMPLE_CONTACTS, PREVIEW_DURATIONS, PREVIEW_SCOPES,
  createPreviewState, advancePreview, beginPreview, endPreview,
} from '../src/preview-session.ts';

const now = 1000000;
const selection = { recipientId: EXAMPLE_CONTACTS[0].id, direction: 'outgoing', scope: 'PRESENCE', durationSeconds: 60 };

test('default is off, and time updates cannot activate a preview', () => {
  const idle = createPreviewState();
  assert.deepEqual(idle, { phase: 'idle', runNumber: 0 });
  assert.equal(advancePreview(idle, now), idle);
  assert.equal(endPreview(idle, now), idle);
});

test('only explicit activation creates a finite, immutable simulation', () => {
  const idle = createPreviewState();
  const state = beginPreview(idle, selection, now);
  assert.equal(state.phase, 'running');
  assert.equal(state.session.startedAtMs, now);
  assert.equal(state.session.expiresAtMs, now + 60000);
  assert.equal(state.session.direction, 'outgoing');
  assert.ok(Object.isFrozen(state) && Object.isFrozen(state.session));
  assert.equal(idle.phase, 'idle');
});

for (const recipientId of ['', 'unknown', 'real-contact', null, 5]) {
  test(`invalid recipient is rejected: ${String(recipientId)}`, () => {
    assert.throws(() => beginPreview(createPreviewState(), { ...selection, recipientId }, now), RangeError);
  });
}

for (const scope of ['', 'precise', 'UNKNOWN', 3, null]) {
  test(`invalid scope is rejected: ${String(scope)}`, () => {
    assert.throws(() => beginPreview(createPreviewState(), { ...selection, scope }, now), RangeError);
  });
}

for (const durationSeconds of [0, 59, 86401, -1, 60.5, '60', true, null, NaN, Infinity]) {
  test(`invalid duration is rejected: ${String(durationSeconds)}`, () => {
    assert.throws(() => beginPreview(createPreviewState(), { ...selection, durationSeconds }, now), RangeError);
  });
}

test('every offered duration and scope is supported, including both duration bounds', () => {
  for (const scope of PREVIEW_SCOPES) for (const { seconds } of PREVIEW_DURATIONS) {
    const state = beginPreview(createPreviewState(), { ...selection, scope, durationSeconds: seconds }, now);
    assert.equal(state.session.expiresAtMs, now + seconds * 1000);
  }
});

test('recipient and direction are isolated; starting another run cannot replace an active run', () => {
  const input = { ...selection };
  const state = beginPreview(createPreviewState(), input, now);
  input.recipientId = EXAMPLE_CONTACTS[1].id;
  assert.equal(state.session.recipientId, EXAMPLE_CONTACTS[0].id);
  assert.throws(() => beginPreview(state, input, now + 1), /End the current/);
  assert.throws(() => beginPreview(createPreviewState(), { ...selection, direction: 'incoming' }, now), RangeError);
  assert.throws(() => beginPreview(createPreviewState(), { ...selection, direction: 'both' }, now), RangeError);
});

test('expiry denies exactly at the deadline and never reactivates, even after clock rollback', () => {
  const running = beginPreview(createPreviewState(), selection, now);
  const expiry = running.session.expiresAtMs;
  assert.equal(advancePreview(running, expiry - 1).phase, 'running');
  const expired = advancePreview(running, expiry);
  assert.equal(expired.phase, 'expired');
  assert.equal(expired.endedAtMs, expiry);
  assert.equal(advancePreview(expired, now), expired);
  assert.equal(advancePreview(expired, expiry + 1000), expired);
  assert.equal(endPreview(expired, expiry + 1000), expired);
});

test('ending is immediate and terminal; another explicit start creates a new run', () => {
  const running = beginPreview(createPreviewState(), selection, now);
  const ended = endPreview(running, now + 1);
  assert.equal(ended.phase, 'cancelled');
  assert.equal(ended.endedAtMs, now + 1);
  assert.equal(advancePreview(ended, now), ended);
  assert.equal(advancePreview(ended, now + 999999), ended);
  assert.equal(endPreview(ended, now + 2), ended);
  const fresh = beginPreview(ended, { ...selection, recipientId: EXAMPLE_CONTACTS[1].id }, now + 2);
  assert.equal(fresh.phase, 'running');
  assert.equal(fresh.runNumber, 2);
  assert.equal(ended.phase, 'cancelled');
});

test('clock rollback cancels immediately without an end before session start', () => {
  const running = beginPreview(createPreviewState(), selection, now);
  const ended = endPreview(running, now - 1);
  assert.equal(ended.phase, 'cancelled');
  assert.equal(ended.endedAtMs, running.session.startedAtMs);
  assert.equal(ended.session, running.session);
  assert.equal(ended.session.expiresAtMs, now + 60000);
  assert.equal(advancePreview(ended, now - 1000), ended);
  assert.equal(advancePreview(ended, running.session.expiresAtMs), ended);
  assert.equal(endPreview(ended, now), ended);
  assert.equal(running.phase, 'running');
});

test('an expired run requires an explicit new start; app restart retains nothing', () => {
  const running = beginPreview(createPreviewState(), selection, now);
  const expired = advancePreview(running, now + 60000);
  assert.equal(beginPreview(expired, selection, now + 60001).runNumber, 2);
  assert.equal(beginPreview(running, selection, now + 60001).runNumber, 2);
  assert.deepEqual(createPreviewState(), { phase: 'idle', runNumber: 0 });
});

test('invalid clocks and unsafe expiry arithmetic are rejected', () => {
  for (const bad of [-1, NaN, Infinity, '1000', 1.1]) {
    assert.throws(() => beginPreview(createPreviewState(), selection, bad), RangeError);
    assert.throws(() => advancePreview(createPreviewState(), bad), RangeError);
    assert.throws(() => endPreview(createPreviewState(), bad), RangeError);
  }
  assert.throws(() => beginPreview(createPreviewState(), selection, Number.MAX_SAFE_INTEGER), RangeError);
});

test('simulation changes have no network side effects or retained arbitrary payload fields', () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = () => { calls++; throw new Error('No network permitted'); };
  try {
    const state = beginPreview(createPreviewState(), { ...selection, arbitrary: { private: true } }, now);
    assert.equal('arbitrary' in state.session, false);
    assert.equal(endPreview(state, now).phase, 'cancelled');
    assert.equal(advancePreview(state, now + 60000).phase, 'expired');
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
