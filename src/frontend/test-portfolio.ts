
import { getPortfolio } from "./app/services/api/portfolio";

async function main() {
  try {
    const portfolio = await getPortfolio();

    console.log("Portfolio API connected!");
    console.log("Cash balance:", portfolio.cash_balance);
    console.log("Holdings:", portfolio.holdings);
    console.log("Holdings value:", portfolio.holdings_value);
    console.log("Total value:", portfolio.total_value);
    console.log("Simulated:", portfolio.simulated);
  } catch (error) {
    console.error("Portfolio API failed:", error);
    process.exitCode = 1;
  }
}

main();
