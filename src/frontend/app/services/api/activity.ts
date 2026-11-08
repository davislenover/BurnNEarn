import type { DailyStepTotal, DailyTotalsRequest, DailyTotalsResponse } from "../../types/activity";

/** Sends one recorded daily total. The server calculates and saves the reward. */
export async function sendTodaysSteps(
    total: DailyStepTotal,
    timeZone: string,
    signal?: AbortSignal,
): Promise<DailyTotalsResponse> {
    const apiUrl = process.env.EXPO_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
    if (!apiUrl) {
        throw new Error("Set EXPO_PUBLIC_API_URL in the frontend .env file to sync steps.");
    }

    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) {
        controller.abort();
    }

    let timedOut = false;
    const timeout = setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, 10_000);

    const request: DailyTotalsRequest = { time_zone: timeZone, totals: [total] };

    try {
        const response = await fetch(`${apiUrl}/v1/me/activity/daily-totals`, {
            method: "PUT",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify(request),
            signal: controller.signal,
        });
        const data: unknown = await response.json().catch(() => null);

        if (!response.ok) {
            // Our backend uses detail.message for domain errors; validation errors may differ.
            const detail = data && typeof data === "object" && "detail" in data ? data.detail : null;
            const message = detail && typeof detail === "object" && "message" in detail
                && typeof detail.message === "string" ? detail.message : null;
            throw new Error(message ?? `Could not sync steps (HTTP ${response.status}).`);
        }

        if (!data || typeof data !== "object" || Array.isArray(data)
            || !("cash_balance" in data) || typeof data.cash_balance !== "string") {
            throw new Error("The server returned an invalid step-sync response.");
        }

        return data as DailyTotalsResponse;
    } catch (cause) {
        if (timedOut) {
            throw new Error("Sending steps timed out. Refresh to try again.");
        }
        throw cause;
    } finally {
        clearTimeout(timeout);
        signal?.removeEventListener("abort", abort);
    }
}
