
import { sendTodaysSteps } from "./app/services/api/activity";

async function main() {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Toronto",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(new Date());

    const part = (type: string) =>
      parts.find((item) => item.type === type)?.value;

    const today = `${part("year")}-${part("month")}-${part("day")}`;

    const response = await sendTodaysSteps(
      {
        activity_date: today,
        activity_type: "steps",
        step_count: 8421,
      },
      "America/Toronto"
    );

    console.log("Step sync successful!");
    console.log("Daily results:", response.totals);
    console.log("Cash balance:", response.cash_balance);
    console.log("Steps per coin:", response.steps_per_coin);
  } catch (error) {
    console.error("Step sync failed:", error);
    process.exitCode = 1;
  }
}

main();
