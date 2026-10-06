export type Direction = 'up' | 'flat' | 'down';

export type FeedbackScore = {
  evidence: number;
  causality: number;
  prediction: number;
  action: number;
  uncertainty: number;
  total: number;
};

export type ForecastFeedback = {
  key: string;
  name: string;
  predicted: Direction;
  actual: Direction | null;
  correct: boolean | null;
};

export type DecisionFeedback = {
  score: FeedbackScore;
  forecasts: ForecastFeedback[];
  strengths: string[];
  improvements: string[];
  foundEvidence: string[];
  reasoningReview: Array<{
    title: string;
    quote: string;
    explanation: string;
    status: 'good' | 'improve';
  }>;
  lesson: string;
  example: string;
};

type EvaluationInput = {
  marketIndex: number;
  predictions: Record<string, Direction>;
  reason: string;
  action: string;
  openedSources: number;
  actualChanges: Record<string, number | null | undefined>;
};

const assets = [
  ['S&P 500', '미국 대표 주식'],
  ['NASDAQ-100', '미국 기술주'],
  ['US 10Y Treasury yield', '미국 10년물 국채금리'],
  ['Broad U.S. Dollar Index', '달러 가치'],
] as const;

const rules = [
  {
    evidence: ['3.5', '3.2', '0.4', '3.8', '주거비', '근원물가', '휘발유'],
    connections: [
      ['물가', '금리', '물가와 금리 경로'],
      ['금리', '주식', '금리와 주식 부담'],
      ['금리', '달러', '금리와 달러 가치'],
    ],
    lesson: '물가 발표는 숫자 하나보다 예상과의 차이, 근원물가, 금리 기대로 이어지는 경로를 함께 보는 것이 중요해요.',
    example: '물가가 전년 대비 3.5%로 이전 3.2%보다 높고, 근원물가도 3.8%로 높은 상태다. 금리 인하 기대가 늦춰질 수 있어 주식에는 부담, 국채금리와 달러에는 상승 압력이 될 가능성이 있다. 다만 이미 반영된 기대와 다른 뉴스도 있으므로 방향을 단정하지 않겠다.',
  },
  {
    evidence: ['4.75', '5.00', '0.50', '0.5', '인하', '자산 축소', '고용', '물가'],
    connections: [
      ['인하', '주식', '금리 인하와 주식 가치 경로'],
      ['자산', '축소', '금리와 별개인 보유자산 축소'],
      ['고용', '인하', '고용 위험과 금리 인하 이유'],
    ],
    lesson: '금리 인하는 할인율을 낮추는 신호지만, 인하의 이유와 사전 기대에 따라 주식, 채권, 달러 반응이 달라질 수 있어요.',
    example: '연준은 정책금리를 0.50%포인트 내려 4.75~5.00%로 조정했다. 물가 진전은 금리 부담을 낮추지만 고용 위험에 대응한 큰 폭 인하라면 경기 우려도 남는다. 보유자산 축소도 계속되므로 모든 자산이 같은 방향으로 움직인다고 단정하지 않겠다.',
  },
  {
    evidence: ['25.6', '256', '4.1', '0.8', '고용', '일자리', '실업률'],
    connections: [
      ['고용', '경기', '고용과 경기 경로'],
      ['고용', '금리', '고용과 금리 기대'],
      ['임금', '물가', '임금과 물가 압력'],
    ],
    lesson: '강한 고용은 기업 실적에는 도움이 될 수 있지만, 빠른 금리 인하 기대를 낮춰 국채금리, 달러와 성장주에 다른 영향을 줄 수 있어요.',
    example: '12월 일자리는 25.6만 개 늘고 실업률은 4.1%를 유지해 고용이 견조했다. 소비와 기업 실적에는 긍정적이지만 빠른 금리 인하 필요성은 약해질 수 있어 국채금리와 달러에는 상승 압력, 성장주에는 부담이 될 가능성이 있다. 두 경로 중 어느 힘이 큰지 추가 자료를 확인하겠다.',
  },
] as const;

export function directionForChange(change: number | null | undefined, key: string): Direction | null {
  if (change === null || change === undefined || !Number.isFinite(change)) return null;
  const threshold = key.includes('10Y') ? 1 : 0.05;
  return change > threshold ? 'up' : change < -threshold ? 'down' : 'flat';
}

export function evaluateDecision(input: EvaluationInput): DecisionFeedback {
  if (!Number.isSafeInteger(input.openedSources) || input.openedSources < 0) {
    throw new RangeError('openedSources must be a nonnegative safe integer');
  }

  const rule = rules[input.marketIndex] ?? rules[0];
  const text = input.reason.trim().toLowerCase();
  const foundEvidence = rule.evidence.filter(term => text.includes(term.toLowerCase()));
  const foundConnections = rule.connections.filter(([a, b]) => text.includes(a) && text.includes(b));
  const connectors = ['때문', '따라서', '영향', '이어', '이로 인해', '반면'].filter(term => text.includes(term));
  const uncertaintyTerms = ['가능', '수 있', '단정', '불확실', '다만', '반면'].filter(term => text.includes(term));

  const forecasts = assets.map(([key, name]) => {
    const actual = directionForChange(input.actualChanges[key], key);
    const predicted = input.predictions[key] ?? 'flat';
    return { key, name, predicted, actual, correct: actual === null ? null : predicted === actual };
  });
  const actualAvailable = forecasts.every(item => item.actual !== null);
  const correctCount = forecasts.filter(item => item.correct === true).length;

  const evidence = Math.min(30, input.openedSources * 8 + foundEvidence.length * 3);
  const causality = Math.min(30, foundConnections.length * 7 + connectors.length * 2);
  const prediction = actualAvailable ? Math.round((correctCount / forecasts.length) * 5) : 0;
  const expectedActions = input.predictions['S&P 500'] === 'up'
    ? ['growth']
    : input.predictions['S&P 500'] === 'down'
      ? ['defensive', 'savings']
      : ['keep', 'savings'];
  const actionAligned = expectedActions.includes(input.action);
  const action = actionAligned ? 25 : input.action === 'keep' ? 15 : 5;
  const uncertainty = Math.min(10, uncertaintyTerms.length * 3 + (text.length >= 80 ? 1 : 0));
  const score = { evidence, causality, prediction, action, uncertainty, total: evidence + causality + prediction + action + uncertainty };

  const strengths: string[] = [];
  if (input.openedSources > 0) strengths.push(`제공된 자료 ${input.openedSources}개를 열어 판단 전에 확인했어요.`);
  if (foundEvidence.length > 0) strengths.push(`근거에 ${foundEvidence.slice(0, 4).join(', ')}을(를) 사용했어요.`);
  if (foundConnections.length > 0) strengths.push(`${foundConnections.map(([, , label]) => label).join(', ')}를 연결했어요.`);
  if (correctCount > 0) strengths.push(`4개 중 ${correctCount}개 시장 방향을 실제 결과와 같게 판단했어요.`);
  if (actionAligned) strengths.push('미국 대표 주식에 대한 예측 방향과 선택한 자산 행동이 일치해요.');

  const improvements: string[] = [];
  if (input.openedSources === 0) improvements.push('제공된 기사나 배경 자료를 먼저 열고, 사용한 수치를 근거에 남겨 보세요.');
  if (foundEvidence.length === 0) improvements.push('판단에 사용한 실제 수치나 이전치와의 비교를 적어 주세요.');
  if (foundConnections.length === 0) improvements.push('지표가 금리, 경기, 자산가격에 이어지는 과정을 한 단계씩 설명해 보세요.');
  if (uncertaintyTerms.length === 0) improvements.push('한 번의 발표만으로 방향을 단정하지 않고 다른 가능성을 함께 적어 보세요.');
  if (!actionAligned) improvements.push('미국 대표 주식의 예측 방향과 실제 자산 행동이 다릅니다. 장기투자, 현금 필요, 위험관리 등 다른 이유가 있다면 그 이유를 명확히 남기는 것이 좋아요.');
  if (strengths.length === 0) strengths.push('예측 방향을 직접 정했다는 점은 출발점이에요. 이제 수치와 인과관계를 더해 보세요.');

  const sentences = input.reason
    .split(/(?<=[.!?요다])\s+|\n+/)
    .map(sentence => sentence.trim())
    .filter(Boolean);
  const quoteFor = (terms: readonly string[]) =>
    sentences.find(sentence => terms.some(term => sentence.toLowerCase().includes(term.toLowerCase())))
    ?? sentences[0]
    ?? '작성한 근거 없음';
  const reasoningReview: DecisionFeedback['reasoningReview'] = [
    foundEvidence.length > 0
      ? {
          title: '수치를 판단 근거로 사용했어요',
          quote: quoteFor(foundEvidence),
          explanation: `${foundEvidence.slice(0, 4).join(', ')}을(를) 직접 언급해 추상적인 예측에 그치지 않았어요. 이전 수치와 예상치의 차이까지 적으면 근거가 더 명확해져요.`,
          status: 'good',
        }
      : {
          title: '수치 근거가 부족해요',
          quote: quoteFor([]),
          explanation: '예측 방향은 있지만, 어떤 발표 수치가 그 예측을 만들었는지 확인하기 어려워요. 기사의 핵심 수치와 비교 기준을 하나 이상 추가해 보세요.',
          status: 'improve',
        },
    foundConnections.length > 0
      ? {
          title: '사실에서 자산 방향으로 이어지는 경로가 보여요',
          quote: quoteFor(foundConnections[0].slice(0, 2)),
          explanation: `${foundConnections.map(([, , label]) => label).join(', ')}를 설명했어요. 중간 단계인 시장금리, 기업이익, 투자심리 중 하나를 더 명시하면 논리가 더 단단해져요.`,
          status: 'good',
        }
      : {
          title: '판단의 중간 단계가 빠져 있어요',
          quote: quoteFor([]),
          explanation: '발표 수치에서 바로 상승 또는 하락 결론으로 건너뛰지 말고, 그 수치가 금리나 경기 기대를 어떻게 바꾸는지를 한 문장으로 연결해 보세요.',
          status: 'improve',
        },
    uncertaintyTerms.length > 0
      ? {
          title: '예측을 단정하지 않았어요',
          quote: quoteFor(uncertaintyTerms),
          explanation: '‘가능성’, ‘다만’ 등의 표현을 사용해 한 번의 발표로 시장을 확정할 수 없다는 점을 반영했어요.',
          status: 'good',
        }
      : {
          title: '반대 가능성을 함께 적어 보세요',
          quote: quoteFor([]),
          explanation: '내 예측이 틀릴 수 있는 조건을 한 가지 적으면, 위험을 감수하는 범위와 대응 계획이 더 명확해져요.',
          status: 'improve',
        },
  ];

  return { score, forecasts, strengths, improvements, foundEvidence, reasoningReview, lesson: rule.lesson, example: rule.example };
}
