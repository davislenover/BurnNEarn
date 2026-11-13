export type DailyStepTotal = {
    activity_date: string;
    activity_type: "steps";
    step_count: number;
};

export type DailyTotalsRequest = {
    time_zone: string;
    totals: DailyStepTotal[];
};

export type DailyTotalResult = DailyStepTotal & {
    counted: boolean;
    reward: string;
    credited_now: string;
};

export type DailyTotalsResponse = {
    totals: DailyTotalResult[];
    cash_balance: string;
    steps_per_coin: number;
};
