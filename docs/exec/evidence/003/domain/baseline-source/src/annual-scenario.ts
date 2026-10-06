// One-year rehearsal uses a fixed educational return path for the simulated portfolio.
// These monthly return assumptions are internal scenario data, not reproduced historical
// S&P 500 / dollar / bond-fund returns. They are applied identically to every counterfactual
// path so that differences come from the user's decisions rather than hidden data changes.
// Historical market moves are kept separately in annualEventChanges only for post-decision review.

export type MonthlyAutoPeriod = {
  label: string;
  etfReturnPct: number;
  dollarReturnPct: number;
  bondReturnPct: number;
};

export type AnnualInterval = {
  key: string;
  start: string;
  end: string;
  periods: MonthlyAutoPeriod[];
  restoreAvailable?: number;
};

function repeatedPeriods(
  key: string,
  start: string,
  end: string,
  labels: string[],
  etfReturnPct: number,
  dollarReturnPct: number,
  bondReturnPct: number,
): AnnualInterval {
  return {
    key,
    start,
    end,
    periods: labels.map(label => ({ label, etfReturnPct, dollarReturnPct, bondReturnPct })),
  };
}

// Fixed educational assumptions used only by the one-year portfolio rehearsal.
// Values are intentionally simple and versioned in code so the same decision always
// produces the same result in the same scenario version.
export const annualIntervals = {
  afterMarket0: repeatedPeriods('afterMarket0', '2024.04.10', '2024.06.20', ['2024.05', '2024.06'], 0.8, 0.2, 0.3),
  afterScholarship: repeatedPeriods('afterScholarship', '2024.06.20', '2024.08.20', ['2024.07', '2024.08'], 0.5, -0.1, 0.4),
  // The September FOMC is a separate decision point. September's automatic
  // deposit lands before that event; October–December follow the new plan.
  afterRepairToMarket1: repeatedPeriods('afterRepairToMarket1', '2024.08.20', '2024.09.18', ['2024.09'], -0.6, 0.3, -0.2),
  afterMarket1: repeatedPeriods('afterMarket1', '2024.09.18', '2024.12.10', ['2024.10', '2024.11', '2024.12'], 0.9, -0.2, 0.5),
  afterIncome: {
    ...repeatedPeriods('afterIncome', '2024.12.10', '2025.01.08', ['2025.01'], -0.7, 0.4, -0.3),
    restoreAvailable: 30,
  },
  afterMarket2: repeatedPeriods('afterMarket2', '2025.01.10', '2025.04.09', ['2025.02', '2025.03', '2025.04'], 0.6, -0.1, 0.4),
} satisfies Record<string, AnnualInterval>;

// Event-day historical reactions are used only after the user commits a judgment.
// They support prediction-vs-actual review and do not drive the 12-month simulated portfolio path.
export const annualEventChanges: Record<string, Record<string, number | null>> = {
  '2024-04-10': {
    'S&P 500': -0.9457,
    'NASDAQ-100': -0.8709,
    'US 10Y Treasury yield': 19,
    'Broad U.S. Dollar Index': 0.719,
  },
  '2024-09-18': {
    'S&P 500': -0.2896,
    'NASDAQ-100': -0.4524,
    'US 10Y Treasury yield': 5,
    'Broad U.S. Dollar Index': -0.034,
  },
  '2025-01-10': {
    'S&P 500': -1.5412,
    'NASDAQ-100': -1.574,
    'US 10Y Treasury yield': 10,
    'Broad U.S. Dollar Index': 0.6104,
  },
};
