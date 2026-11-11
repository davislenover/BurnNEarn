export type DailyStepTotal = {
    activity_date: string;
    activity_type: "steps";
    step_count: number;
};

export type DailyTotalsRequest = {
    time_zone: string;
    totals: DailyStepTotal[];
};

export type DailyTotalsResponse = {
    cash_balance: string;
    // Preserve the per-day results without assuming their wrapper before #190 is implemented.
    [field: string]: unknown;
};
