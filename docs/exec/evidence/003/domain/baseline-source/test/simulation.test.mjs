import assert from 'node:assert/strict';
import test from 'node:test';
import { allocationForStrategy, applyFinanceAction, copyFinance, monthlyGap, netAssets, replayChoice, sumMoney } from '../src/simulation.ts';
import { evaluateDecision } from '../src/decision-feedback.ts';
import { annualEventChanges, annualIntervals } from '../src/annual-scenario.ts';

const initial = () => ({ portfolio: { cash: 80, savings: 60, etf: 40, bond: 20, dollar: 0 }, allocation: { cash: 10, savings: 10, etf: 5, bond: 5 }, available: 30, debt: 0, monthlyPayment: 0, reservedCash: 0 });

for (const choice of ['비상금', '적금', 'S&P 500 ETF', '채권', '달러', '현금', '소비']) {
  test(`bonus is conserved and history is immutable: ${choice}`, () => {
    const before = initial();
    const result = applyFinanceAction(before, { kind: 'scholarship', choice, amount: 40 });
    assert.deepEqual(before, initial());
    assert.equal(netAssets(result.after), choice === '소비' ? 200 : 240);
    assert.equal(result.after.available, 30);
    if (choice === '달러') assert.equal(result.after.portfolio.dollar, 40);
    result.after.portfolio.cash = 0;
    assert.equal(before.portfolio.cash, 80);
  });
}

for (const choice of ['비상금', '적금 중도해지', '투자자산 매도', '카드 할부', '소비 축소']) {
  test(`repair cost is never erased: ${choice}`, () => {
    const before = initial();
    const { after } = applyFinanceAction(before, { kind: 'repair', choice, amount: 60 });
    assert.equal(netAssets(before) - netAssets(after), 60);
    assert.ok(Object.values(after.portfolio).every(v => v >= 0));
    if (choice === '카드 할부') {
      assert.equal(sumMoney(after.portfolio), 200);
      assert.equal(after.debt, 60);
      assert.equal(after.monthlyPayment, 10);
    } else assert.equal(after.debt, 0);
  });
}

test('insufficient preferred asset uses explicitly described secondary funds without minting money', () => {
  const before = initial(); before.portfolio.savings = 10;
  const { after, explanation } = applyFinanceAction(before, { kind: 'repair', choice: '적금 중도해지', amount: 60 });
  assert.equal(after.portfolio.savings, 0);
  assert.equal(after.portfolio.cash, 30);
  assert.equal(netAssets(before) - netAssets(after), 60);
  assert.ok(explanation.some(text => text.includes('보충')));
});

test('an impossible repair is rejected instead of clipping the cost', () => {
  const before = initial(); before.portfolio = { cash: 1, savings: 0, etf: 0, bond: 0, dollar: 0 };
  assert.throws(() => applyFinanceAction(before, { kind: 'repair', choice: '비상금', amount: 60 }), /부족/);
});

for (const choice of ['ETF 축소', '적금 축소', '소비 축소']) {
  test(`income reduction keeps allocation within actual resources: ${choice}`, () => {
    const { after } = applyFinanceAction(initial(), { kind: 'income', choice, available: 5 });
    assert.equal(after.available, 5);
    assert.equal(sumMoney(after.allocation), 5);
    assert.equal(netAssets(after), 200);
    assert.equal(monthlyGap(after), 0);
  });
}

test('keeping an unaffordable plan exposes the gap; reserving cash does not double-count assets', () => {
  const kept = applyFinanceAction(initial(), { kind: 'income', choice: '기존 계획 유지', available: 5 }).after;
  assert.equal(monthlyGap(kept), 25);
  const reserved = applyFinanceAction(initial(), { kind: 'income', choice: '비상금 사용', available: 5 }).after;
  assert.equal(reserved.reservedCash, 25);
  assert.equal(netAssets(reserved), 200);
  assert.equal(monthlyGap(reserved), 0);
  const repaired = applyFinanceAction(reserved, { kind: 'repair', choice: '비상금', amount: 60 }).after;
  assert.equal(repaired.reservedCash, 20);
  assert.equal(monthlyGap(repaired), 5);
});

test('post-news actions change the monthly strategy without instantly trading existing holdings', () => {
  const before = initial();
  const after = applyFinanceAction(before, { kind: 'review', choice: 'defensive' }).after;
  assert.deepEqual(after.portfolio, before.portfolio);
  assert.equal(sumMoney(after.portfolio), sumMoney(before.portfolio));
  assert.deepEqual(after.allocation, { cash: 15, savings: 11, etf: 0, bond: 4 });
  assert.deepEqual(after.strategyPlan, after.allocation);
  assert.equal(after.strategy, 'defensive');
});

test('a savings choice changes the next monthly deposit mix without changing current assets', () => {
  const before = initial();
  const after = applyFinanceAction(before, { kind: 'review', choice: 'savings' }).after;
  assert.deepEqual(after.portfolio, before.portfolio);
  assert.deepEqual(after.allocation, { cash: 6, savings: 20, etf: 2, bond: 2 });
  assert.equal(sumMoney(after.portfolio), sumMoney(before.portfolio));
});

test('the announcement-day result affects only holdings that existed before the new strategy', () => {
  const conservative = applyFinanceAction(initial(), { kind: 'review', choice: 'defensive' }).after;
  const growth = applyFinanceAction(initial(), { kind: 'review', choice: 'growth' }).after;
  const conservativeResult = applyFinanceAction(conservative, { kind: 'market', etfReturnPct: 5, dollarReturnPct: 2 }).after;
  const growthResult = applyFinanceAction(growth, { kind: 'market', etfReturnPct: 5, dollarReturnPct: 2 }).after;
  assert.equal(conservativeResult.portfolio.etf, 42);
  assert.equal(growthResult.portfolio.etf, 42);
  assert.equal(netAssets(growthResult), netAssets(conservativeResult));
});

test('the selected strategy changes later automatic deposits and their market exposure', () => {
  const defensive = applyFinanceAction(initial(), { kind: 'review', choice: 'defensive' }).after;
  const growth = applyFinanceAction(initial(), { kind: 'review', choice: 'growth' }).after;
  const period = { kind: 'auto', periods: [{ label: '다음 달', etfReturnPct: -10, dollarReturnPct: 0, bondReturnPct: 0 }] };
  const defensiveResult = applyFinanceAction(defensive, period).after;
  const growthResult = applyFinanceAction(growth, period).after;
  assert.equal(defensiveResult.portfolio.etf, 36);
  assert.equal(growthResult.portfolio.etf, 51.3);
  assert.ok(netAssets(defensiveResult) > netAssets(growthResult));
});

test('the complete annual calendar contains exactly twelve automatic monthly deposits', () => {
  const intervals = Object.values(annualIntervals);
  assert.equal(intervals.reduce((sum, interval) => sum + interval.periods.length, 0), 12);
  assert.deepEqual(Object.keys(annualEventChanges), ['2024-04-10', '2024-09-18', '2025-01-10']);
  assert.ok(new Date(intervals[0].start) < new Date(intervals.at(-1).end));
});

test('a temporary income decrease restores the last chosen strategy after one reduced month', () => {
  const growth = applyFinanceAction(initial(), { kind: 'review', choice: 'growth' }).after;
  const reduced = applyFinanceAction(growth, { kind: 'income', choice: 'ETF 축소', available: 5 }).after;
  assert.deepEqual(reduced.allocation, { cash: 5, savings: 0, etf: 0, bond: 0 });
  const restored = applyFinanceAction(reduced, {
    kind: 'auto',
    periods: [{ label: '2025.01', etfReturnPct: 0, dollarReturnPct: 0, bondReturnPct: 0 }],
    restoreAvailable: 30,
  }).after;
  assert.equal(restored.available, 30);
  assert.deepEqual(restored.allocation, allocationForStrategy(30, 'growth', growth.allocation));
});

test('a correct forecast never creates bonus money', () => {
  const before = initial();
  const { after } = applyFinanceAction(before, { kind: 'market', etfReturnPct: -0.95, dollarReturnPct: 0.72 });
  assert.equal(after.portfolio.etf, 39.62);
  assert.equal(after.portfolio.dollar, 0);
  assert.equal(after.portfolio.cash, 80);
});

test('restoring a checkpoint and changing a decision replaces, rather than duplicates, its effect', () => {
  const checkpoint = copyFinance(initial());
  const first = applyFinanceAction(checkpoint, { kind: 'scholarship', choice: '적금', amount: 40 }).after;
  const changed = applyFinanceAction(copyFinance(checkpoint), { kind: 'scholarship', choice: 'S&P 500 ETF', amount: 40 }).after;
  assert.equal(first.portfolio.savings, 100);
  assert.equal(changed.portfolio.savings, 60);
  assert.equal(changed.portfolio.etf, 80);
  assert.equal(netAssets(changed), 240);
});

const actualChanges = {
  'S&P 500': -0.95,
  'NASDAQ-100': -0.84,
  'US 10Y Treasury yield': 19,
  'Broad U.S. Dollar Index': 0.72,
};

test('reasoning with sources, evidence and causal links scores above an unsupported guess', () => {
  const reasoned = evaluateDecision({
    marketIndex: 0,
    predictions: { 'S&P 500': 'down', 'NASDAQ-100': 'down', 'US 10Y Treasury yield': 'up', 'Broad U.S. Dollar Index': 'up' },
    reason: '물가가 3.5%로 3.2%보다 높고 근원물가도 3.8%다. 때문에 금리 인하가 늦어져 주식에 부담이 될 수 있다. 다만 이미 반영됐을 가능성도 있어 단정하지 않겠다.',
    action: 'defensive',
    openedSources: 2,
    actualChanges,
  });
  const guessed = evaluateDecision({
    marketIndex: 0,
    predictions: { 'S&P 500': 'down', 'NASDAQ-100': 'down', 'US 10Y Treasury yield': 'up', 'Broad U.S. Dollar Index': 'up' },
    reason: '', action: 'defensive', openedSources: 0, actualChanges,
  });
  assert.ok(reasoned.score.total > guessed.score.total);
  assert.equal(reasoned.score.prediction, guessed.score.prediction);
  assert.ok(reasoned.strengths.some(item => item.includes('3.5')));
  assert.ok(reasoned.reasoningReview.some(item => item.quote.includes('3.5')));
  assert.ok(reasoned.reasoningReview.every(item => item.explanation.length > 20));
});

test('forecast luck is capped and never outweighs a well-supported judgment process', () => {
  const lucky = evaluateDecision({
    marketIndex: 0,
    predictions: { 'S&P 500': 'down', 'NASDAQ-100': 'down', 'US 10Y Treasury yield': 'up', 'Broad U.S. Dollar Index': 'up' },
    reason: '', action: 'defensive', openedSources: 0, actualChanges,
  });
  assert.equal(lucky.score.prediction, 5);
  assert.ok(lucky.score.total <= 30);
  assert.equal(lucky.forecasts[2].name, '미국 10년물 국채금리');
});

test('forecast results stay locked until actual market changes are supplied', () => {
  const locked = evaluateDecision({
    marketIndex: 0,
    predictions: { 'S&P 500': 'down', 'NASDAQ-100': 'down', 'US 10Y Treasury yield': 'up', 'Broad U.S. Dollar Index': 'up' },
    reason: '물가와 금리의 영향을 연결해 가능성을 적었습니다.',
    action: 'defensive',
    openedSources: 1,
    actualChanges: {},
  });

  assert.equal(locked.score.prediction, 0);
  assert.ok(locked.forecasts.every(item => item.actual === null && item.correct === null));
});

test('an action aligned with the stock forecast receives a higher consistency score', () => {
  const base = {
    marketIndex: 0,
    predictions: { 'S&P 500': 'down', 'NASDAQ-100': 'flat', 'US 10Y Treasury yield': 'flat', 'Broad U.S. Dollar Index': 'flat' },
    reason: '물가와 금리의 영향을 보고 주식은 하락 가능성이 있다.', openedSources: 1, actualChanges,
  };
  const aligned = evaluateDecision({ ...base, action: 'defensive' });
  const opposed = evaluateDecision({ ...base, action: 'growth' });
  assert.equal(aligned.score.action, 25);
  assert.ok(aligned.score.action > opposed.score.action);
});

test('counterfactual paths replay the same future events after different asset choices', () => {
  const future = [
    { kind: 'scholarship', choice: '현금', amount: 40 },
    { kind: 'auto', periods: [{ label: '다음 달', etfReturnPct: 5, dollarReturnPct: 0, bondReturnPct: 0 }] },
  ];
  const defensive = replayChoice(initial(), { kind: 'review', choice: 'defensive' }, future);
  const growth = replayChoice(initial(), { kind: 'review', choice: 'growth' }, future);
  assert.equal(defensive.valid, true);
  assert.equal(growth.valid, true);
  assert.ok(defensive.after.portfolio.cash > growth.after.portfolio.cash);
  assert.ok(growth.after.portfolio.etf > defensive.after.portfolio.etf);
  assert.notEqual(netAssets(growth.after), netAssets(defensive.after));
});

test('counterfactual emergency choices expose debt and liquidity tradeoffs', () => {
  const cash = replayChoice(initial(), { kind: 'repair', choice: '비상금', amount: 60 }, []);
  const installment = replayChoice(initial(), { kind: 'repair', choice: '카드 할부', amount: 60 }, []);
  assert.equal(netAssets(cash.after), netAssets(installment.after));
  assert.equal(cash.after.portfolio.cash, 20);
  assert.equal(installment.after.portfolio.cash, 80);
  assert.equal(installment.after.debt, 60);
  assert.equal(installment.after.monthlyPayment, 10);
});
