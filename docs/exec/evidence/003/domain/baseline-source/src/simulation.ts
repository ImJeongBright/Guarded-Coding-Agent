export type PlanKey = 'cash' | 'savings' | 'etf' | 'bond';
export type AssetKey = PlanKey | 'dollar';
export type Plan = Record<PlanKey, number>;
export type FinanceState = {
  portfolio: Record<AssetKey, number>;
  allocation: Plan;
  available: number;
  debt: number;
  monthlyPayment: number;
  reservedCash: number;
  strategy?: string;
  strategyPlan?: Plan;
};
export type MonthlyAutoPeriod = {
  label: string;
  etfReturnPct: number;
  dollarReturnPct: number;
  bondReturnPct: number;
};
export type FinanceAction =
  | { kind: 'plan'; allocation: Plan }
  | { kind: 'market'; etfReturnPct: number | null; dollarReturnPct: number | null }
  | { kind: 'review'; choice: string }
  | { kind: 'auto'; periods: MonthlyAutoPeriod[]; restoreAvailable?: number }
  | { kind: 'scholarship'; choice: string; amount: number }
  | { kind: 'income'; choice: string; available: number }
  | { kind: 'repair'; choice: string; amount: number };
export type DecisionRecord = {
  phase: number;
  kind: 'plan' | 'market' | 'trade' | 'life' | 'auto';
  marketIndex?: number;
  action: FinanceAction;
  title: string;
  date: string;
  choice: string;
  before: FinanceState;
  after: FinanceState;
  explanation: string[];
};

export type ChoiceOutcome = {
  choice: string;
  after: FinanceState;
  valid: boolean;
  error?: string;
};

export const assetLabels: Record<AssetKey, string> = {
  cash: '현금·파킹', savings: '적금', etf: '주식 ETF', bond: '채권 ETF', dollar: '달러 보유액(원화 환산)',
};
export const sumMoney = (values: Record<string, number>) =>
  Math.round(Object.values(values).reduce((sum, value) => sum + value, 0) * 100) / 100;
export const netAssets = (state: FinanceState) => sumMoney(state.portfolio) - state.debt;
export const monthlyGap = (state: FinanceState) =>
  Math.max(0, sumMoney(state.allocation) + state.monthlyPayment - state.available - state.reservedCash);
export const copyFinance = (state: FinanceState): FinanceState => ({
  ...state,
  portfolio: { ...state.portfolio },
  allocation: { ...state.allocation },
  strategyPlan: state.strategyPlan ? { ...state.strategyPlan } : undefined,
});

function allocationFromRatios(available: number, ratios: Plan): Plan {
  const cash = Math.round(available * ratios.cash);
  const savings = Math.round(available * ratios.savings);
  const etf = Math.round(available * ratios.etf);
  return { cash, savings, etf, bond: available - cash - savings - etf };
}

export function allocationForStrategy(available: number, choice: string, current: Plan): Plan {
  if (choice === 'keep') return { ...current };
  if (choice === 'defensive') return allocationFromRatios(available, { cash: 0.5, savings: 0.35, etf: 0, bond: 0.15 });
  if (choice === 'savings') return allocationFromRatios(available, { cash: 0.2, savings: 0.65, etf: 0.05, bond: 0.1 });
  if (choice === 'growth') return allocationFromRatios(available, { cash: 0.15, savings: 0.15, etf: 0.55, bond: 0.15 });
  return { ...current };
}

function scalePlan(plan: Plan, available: number): Plan {
  const total = sumMoney(plan);
  if (total <= 0) return allocationFromRatios(available, { cash: 1, savings: 0, etf: 0, bond: 0 });
  return allocationFromRatios(available, {
    cash: plan.cash / total,
    savings: plan.savings / total,
    etf: plan.etf / total,
    bond: plan.bond / total,
  });
}

// Units are 만 원. Automatic periods execute the active allocation once per month.
// Cash/savings use the fictional product rates; ETF/dollar use historical period returns;
// bonds use the disclosed educational duration proxy. Taxes, fees and FX spread are omitted.
export function applyFinanceAction(before: FinanceState, action: FinanceAction) {
  const after = copyFinance(before);
  const explanation: string[] = [];
  if (action.kind === 'plan') {
    if (sumMoney(action.allocation) !== before.available) throw new Error('월 가용금액에 맞춰 배분해 주세요.');
    after.allocation = { ...action.allocation };
    after.strategyPlan = { ...action.allocation };
    explanation.push(`월 ${before.available}만 원의 배분 계획을 저장했어요. 아직 자동이체를 실행한 것은 아니므로 보유자산은 변하지 않았어요.`);
  }
  if (action.kind === 'market') {
    const changes: string[] = [];
    const applyReturn = (key: 'etf' | 'dollar', returnPct: number | null) => {
      if (returnPct === null || after.portfolio[key] === 0) return;
      const previous = after.portfolio[key];
      after.portfolio[key] = Math.round(previous * (1 + returnPct / 100) * 100) / 100;
      const change = Math.round((after.portfolio[key] - previous) * 100) / 100;
      changes.push(`${assetLabels[key]} ${previous}만 원 × ${returnPct > 0 ? '+' : ''}${returnPct.toFixed(2)}% = ${change > 0 ? '+' : ''}${change}만 원`);
    };
    applyReturn('etf', action.etfReturnPct);
    applyReturn('dollar', action.dollarReturnPct);
    explanation.push(changes.length
      ? `보유하고 있던 자산에 발표 당일의 실제 등락률을 반영했어요: ${changes.join(' · ')}`
      : '반영할 ETF나 달러 보유액이 없어 이번 시장 변화로 인한 자산 변동은 없었어요.');
    explanation.push('예측을 맞혔다는 이유로 보상을 주지 않았어요. 오직 이미 보유한 금액과 실제 시장 변화만 계산했어요.');
    explanation.push('채권 ETF는 국채금리와 같은 자산이 아니며 실제 상품 가격 자료가 없어 이번 등락 계산에서 제외했어요.');
  }
  if (action.kind === 'review') {
    after.strategy = action.choice;
    after.allocation = allocationForStrategy(after.available, action.choice, after.allocation);
    after.strategyPlan = { ...after.allocation };
    explanation.push(action.choice === 'keep'
      ? '현재의 월 자동 납입 비중을 그대로 유지했어요.'
      : `다음 금융 이슈까지 매월 현금 ${after.allocation.cash}만 원, 적금 ${after.allocation.savings}만 원, ETF ${after.allocation.etf}만 원, 채권 ${after.allocation.bond}만 원을 자동 납입하도록 바꿨어요.`);
    explanation.push('기존 보유자산을 한 번에 매매하지 않고, 이후 월 납입부터 새 방향을 적용해 판단이 시간에 따라 누적되도록 했어요.');
  }
  if (action.kind === 'auto') {
    const startingAssets = sumMoney(after.portfolio);
    let outsideContribution = 0;
    for (const period of action.periods) {
      const planned = sumMoney(after.allocation);
      const supplement = Math.max(0, planned - after.available);
      if (supplement > 0) {
        if (after.reservedCash < supplement || after.portfolio.cash < supplement) throw new Error('자동 납입에 사용할 비상금이 부족해요. 월 계획을 줄여야 합니다.');
        after.portfolio.cash = Math.round((after.portfolio.cash - supplement) * 100) / 100;
      }
      outsideContribution += Math.min(planned, after.available);
      (Object.keys(after.allocation) as PlanKey[]).forEach(key => {
        after.portfolio[key] = Math.round((after.portfolio[key] + after.allocation[key]) * 100) / 100;
      });
      const monthlyReturns: Partial<Record<AssetKey, number>> = {
        cash: 2.3 / 12,
        savings: 4.2 / 12,
        etf: period.etfReturnPct,
        bond: period.bondReturnPct,
        dollar: period.dollarReturnPct,
      };
      (Object.keys(monthlyReturns) as AssetKey[]).forEach(key => {
        const rate = monthlyReturns[key] ?? 0;
        after.portfolio[key] = Math.round(after.portfolio[key] * (1 + rate / 100) * 100) / 100;
      });
    }
    const marketAndInterest = Math.round((sumMoney(after.portfolio) - startingAssets - outsideContribution) * 100) / 100;
    explanation.push(`${action.periods[0]?.label ?? ''}${action.periods.length > 1 ? `~${action.periods.at(-1)?.label}` : ''} 동안 ${action.periods.length}개월 자동 납입을 실행했어요. 외부에서 들어온 돈은 총 ${outsideContribution}만 원이에요.`);
    explanation.push(`같은 기간의 시장 흐름과 예·적금 이자를 반영한 평가 변화는 ${marketAndInterest >= 0 ? '+' : ''}${marketAndInterest}만 원이에요.`);
    if (action.restoreAvailable !== undefined) {
      after.available = action.restoreAvailable;
      after.reservedCash = 0;
      after.allocation = scalePlan(after.strategyPlan ?? after.allocation, after.available);
      explanation.push(`시험기간이 끝나 월 운용 가능금액을 ${action.restoreAvailable}만 원으로 되돌리고, 마지막 금융 이슈에서 정한 전략을 다시 적용했어요.`);
    }
  }
  if (action.kind === 'scholarship') {
    if (action.choice === '소비') {
      explanation.push(`추가 수입 ${action.amount}만 원을 받아 모두 소비했어요. 수입과 지출이 같아 금융자산의 순변화는 0만 원이에요.`);
    } else {
      const destination: AssetKey = action.choice === 'S&P 500 ETF' ? 'etf'
        : action.choice === '적금' ? 'savings' : action.choice === '채권' ? 'bond'
          : action.choice === '달러' ? 'dollar' : 'cash';
      after.portfolio[destination] += action.amount;
      explanation.push(`추가 수입 ${action.amount}만 원을 ${assetLabels[destination]}에 배정해 금융자산이 그만큼 늘었어요.`);
      if (destination === 'dollar') explanation.push('달러는 원화와 구분해 원화 환산 취득액으로 기록했어요. 환율 변화와 환전 비용은 이번 계산에 포함하지 않았어요.');
    }
    explanation.push('일회성 수입이므로 매달 반복되는 가용금액은 바뀌지 않아요.');
  }
  if (action.kind === 'income') {
    after.available = action.available;
    after.reservedCash = 0;
    const gap = Math.max(0, sumMoney(before.allocation) + before.monthlyPayment - action.available);
    explanation.push(`소득 감소로 월 가용금액이 ${before.available}만 원에서 ${action.available}만 원으로 줄었어요. 아직 월 납입을 실행하지 않았으므로 보유자산은 그대로예요.`);
    if (action.choice === '기존 계획 유지') {
      explanation.push(`월 계획은 유지했지만 ${gap}만 원의 부족분이 남아요. 이 금액은 확보된 돈으로 계산하지 않았어요.`);
    } else if (action.choice === '비상금 사용') {
      if (after.portfolio.cash < gap) throw new Error('부족분을 충당할 현금·파킹 잔액이 모자라요. 납입 계획을 줄이는 선택이 필요해요.');
      after.reservedCash = gap;
      explanation.push(`비상금 ${gap}만 원을 이번 달 부족분에 쓰도록 예약했어요. 아직 출금하지 않았으며, 이후 다른 지출에 쓰면 부족분이 다시 생겨요.`);
    } else {
      let reduction = Math.max(0, sumMoney(after.allocation) - Math.max(0, action.available - after.monthlyPayment));
      const priority: PlanKey[] = action.choice === '적금 축소'
        ? ['savings', 'etf', 'bond', 'cash'] : ['etf', 'bond', 'savings', 'cash'];
      for (const key of priority) {
        const cut = Math.min(reduction, after.allocation[key]);
        after.allocation[key] -= cut;
        reduction -= cut;
      }
      explanation.push(action.choice === '적금 축소'
        ? '적금을 먼저 줄이고, 부족하면 ETF·채권 순서로 줄여 가용금액에 맞췄어요.'
        : 'ETF·채권 적립을 먼저 줄이고, 부족하면 적금을 줄여 현금 여유를 우선 남겼어요.');
      if (action.choice === '소비 축소') explanation.push('소비를 줄이려는 계획은 기록했지만 절감액이 확정되지 않아 추가 현금으로 잡지 않았어요. 우선 확정된 가용금액 안으로 납입도 조정했어요.');
    }
  }
  if (action.kind === 'repair') {
    if (action.choice === '카드 할부') {
      after.debt += action.amount;
      after.monthlyPayment += action.amount / 6;
      explanation.push(`수리비 ${action.amount}만 원이 할부 잔액으로 생겼어요. 금융자산은 유지되지만 순자산은 ${action.amount}만 원 줄었어요.`);
      explanation.push(`교육용으로 6개월 균등원금 상환을 가정해 월 ${action.amount / 6}만 원의 추가 부담을 기록했어요. 실제 할부 수수료는 별도이며 이번 계산에는 포함하지 않았어요.`);
    } else {
      if (sumMoney(after.portfolio) < action.amount) throw new Error('수리비를 전액 지급할 금융자산이 부족해요. 현재 선택으로는 진행할 수 없어요.');
      const order: AssetKey[] = action.choice === '적금 중도해지' ? ['savings', 'cash', 'etf', 'bond', 'dollar']
        : action.choice === '투자자산 매도' ? ['etf', 'bond', 'cash', 'savings', 'dollar']
          : ['cash', 'savings', 'etf', 'bond', 'dollar'];
      let remaining = action.amount;
      const used: string[] = [];
      for (const key of order) {
        const amount = Math.min(after.portfolio[key], remaining);
        after.portfolio[key] -= amount;
        remaining -= amount;
        if (amount) used.push(`${assetLabels[key]} ${amount}만 원`);
      }
      after.reservedCash = Math.min(after.reservedCash, after.portfolio.cash);
      explanation.push(`${used.join(' + ')}에서 총 ${action.amount}만 원을 지급했어요. 금융자산과 순자산이 모두 ${action.amount}만 원 줄었어요.`);
      if (used.length > 1) explanation.push('우선 선택한 자산만으로 부족한 금액은 다른 자산에서 보충했어요. 각 항목의 실제 차감액을 아래에서 확인할 수 있어요.');
      if (action.choice === '소비 축소') explanation.push('즉시 필요한 수리비는 우선 보유자산으로 지급했어요. 앞으로 줄일 소비는 아직 실현되지 않아 자산에 더하지 않았어요.');
      if (action.choice !== '비상금') explanation.push('중도해지 이자 감소, 매도 수수료·세금 및 환전 비용은 미반영한 원금 기준 비교예요.');
    }
  }
  if (monthlyGap(after) > 0) explanation.push(`현재 계획대로라면 이번 달 ${monthlyGap(after)}만 원이 부족해요. 자금 부족이 해결된 것으로 처리하지 않았어요.`);
  return { after, explanation };
}

export function replayChoice(
  before: FinanceState,
  firstAction: FinanceAction,
  futureActions: FinanceAction[],
): ChoiceOutcome {
  try {
    let state = applyFinanceAction(copyFinance(before), firstAction).after;
    for (const action of futureActions) {
      state = applyFinanceAction(state, action).after;
    }
    return {
      choice: 'choice' in firstAction ? firstAction.choice : firstAction.kind,
      after: state,
      valid: true,
    };
  } catch (error) {
    return {
      choice: 'choice' in firstAction ? firstAction.choice : firstAction.kind,
      after: copyFinance(before),
      valid: false,
      error: error instanceof Error ? error.message : '이 경로는 계산할 수 없어요.',
    };
  }
}
