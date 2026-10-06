import assert from 'node:assert/strict';
import test from 'node:test';
import { directionForChange, evaluateDecision } from '../src/decision-feedback.ts';

const keys = ['S&P 500', 'NASDAQ-100', 'US 10Y Treasury yield', 'Broad U.S. Dollar Index'];
const freezeInput = input => {
  Object.freeze(input.predictions);
  Object.freeze(input.actualChanges);
  return Object.freeze(input);
};

test('decision regression: malformed source counts reject without changing inputs', () => {
  for (const openedSources of [-Number.MAX_SAFE_INTEGER, -Number.MIN_VALUE, 1.5,
    Number.MAX_SAFE_INTEGER + 1, Number.MAX_VALUE, NaN, Infinity, -Infinity,
    '', '0', '9007199254740991', null, undefined, false, [], {}, 0n, Symbol('count')]) {
    const input = freezeInput({
      marketIndex: 0, predictions: { 'S&P 500': 'up' }, reason: '3.5',
      action: 'growth', openedSources, actualChanges: { 'S&P 500': Infinity },
    });
    const before = { ...input, predictions: { ...input.predictions }, actualChanges: { ...input.actualChanges } };
    assert.throws(() => evaluateDecision(input), {
      name: 'RangeError', message: 'openedSources must be a nonnegative safe integer',
    });
    assert.deepEqual(input, before);
  }
});

test('decision regression: direction boundaries include adjacent finite values', () => {
  for (const key of keys) {
    const threshold = key.includes('10Y') ? 1 : 0.05;
    // One representable step at each threshold (spacing below 1 is half that above).
    const above = key.includes('10Y') ? 1 + Number.EPSILON : 0.05000000000000001;
    const below = key.includes('10Y') ? 1 - Number.EPSILON / 2 : 0.049999999999999996;
    assert.ok(below < threshold && above > threshold);
    for (const [change, expected] of [
      [-above, 'down'], [-threshold, 'flat'], [-below, 'flat'],
      [-Number.MIN_VALUE, 'flat'], [-0, 'flat'], [0, 'flat'],
      [Number.MIN_VALUE, 'flat'], [below, 'flat'], [threshold, 'flat'], [above, 'up'],
    ]) {
      assert.equal(directionForChange(change, key), expected, `${key}: ${change}`);
      const input = freezeInput({
        marketIndex: 0, predictions: Object.fromEntries(keys.map(asset => [asset, expected])),
        reason: '', action: 'keep', openedSources: 0,
        actualChanges: Object.fromEntries(keys.map(asset => [asset, asset === key ? change : 0])),
      });
      const before = structuredClone(input);
      const forecast = evaluateDecision(input).forecasts.find(item => item.key === key);
      assert.equal(forecast.actual, expected);
      assert.equal(forecast.correct, true);
      assert.deepEqual(input, before);
    }
  }
});

test('decision regression: deterministic score properties and input immutability', () => {
  const reasons = [
    '',
    '3.5 3.2 0.4 3.8 주거비 근원물가 휘발유 물가 금리 주식 달러 때문에 따라서 영향 이어 이로 인해 반면 가능 수 있 단정 불확실 다만 ' + '설명'.repeat(40),
    '4.75 5.00 0.50 0.5 인하 자산 축소 고용 물가 주식 때문에 따라서 영향 가능 다만',
    '25.6 256 4.1 0.8 고용 일자리 실업률 경기 금리 임금 물가 때문에 반면 단정',
  ];
  const changes = [-Number.MAX_VALUE, -1, -0.05, -0, 0.05, 1, Number.MAX_VALUE,
    NaN, Infinity, -Infinity, null, undefined];
  let cases = 0;
  let reachedMaximum = false;
  for (const openedSources of [0, -0, 1, 2, 3, 4, 5, 1024, Number.MAX_SAFE_INTEGER - 1, Number.MAX_SAFE_INTEGER]) {
    for (const marketIndex of [0, 1, 2, 99]) {
      for (const reason of reasons) {
        for (const direction of ['down', 'flat', 'up']) {
          for (const action of ['growth', 'defensive', 'savings', 'keep']) {
            for (const change of changes) {
              const input = freezeInput({
                marketIndex, reason, openedSources, action,
                predictions: Object.fromEntries(keys.map(key => [key, direction])),
                actualChanges: Object.fromEntries(keys.map(key => [key, change])),
              });
              const before = structuredClone(input);
              const feedback = evaluateDecision(input);
              for (const [name, value] of Object.entries(feedback.score)) {
                assert.ok(Number.isFinite(value) && value >= 0 && value <= 100, name);
              }
              const { total, ...components } = feedback.score;
              assert.equal(total, Object.values(components).reduce((sum, value) => sum + value, 0));
              if (reason === '') assert.equal(feedback.score.evidence, [0, 8, 16, 24][openedSources] ?? 30);
              if (change == null || !Number.isFinite(change)) {
                assert.equal(feedback.score.prediction, 0);
                assert.ok(feedback.forecasts.every(item => item.actual === null && item.correct === null));
              }
              assert.deepEqual(input, before);
              assert.deepEqual(evaluateDecision(input), feedback);
              reachedMaximum ||= total === 100;
              cases++;
            }
          }
        }
      }
    }
  }
  assert.equal(cases, 23040);
  assert.equal(reachedMaximum, true);
});
