export type DailyStepTotal = {
    activity_date: string;
    activity_type: "steps";
    step_count: number;
};

export type DailyTotalsRequest = {
    time_zone: string;
    totals: DailyStepTotal[];
};
