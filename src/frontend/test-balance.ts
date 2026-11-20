
import { getBalance } from "./app/services/api/balance";

async function main() {
  try {
    const response = await getBalance();

    console.log("Balance API connected!");
    console.log("Cash balance:", response.cash_balance);
  } catch (error) {
    console.error("Balance API failed:", error);
    process.exitCode = 1;
  }
}

main();
