

import { buyShares } from "./app/services/api/trading";
import { getAssets } from "./app/services/api/market";
import { getPortfolio } from "./app/services/api/portfolio";

async function main() {
  try {
    const market = await getAssets();

    if (!market.market_open) {
      console.log("Market closed. Cannot buy shares.");
      return;
    }

    const stock = market.assets.find(
      (asset) => asset.symbol === "NVDA"
    );

    if (!stock || stock.price === null || stock.delayed) {
      console.log("Stock price unavailable or delayed.");
      return;
    }

    const request = {
      request_id: crypto.randomUUID(),
      symbol: stock.symbol,
      trade_type: "buy" as const,
      quantity: 1,
      expected_price: stock.price,
    };

    console.log("Buying:", request.symbol);
    console.log("Expected price:", request.expected_price);

    const result = await buyShares(request);

    console.log("Purchase successful!");
    console.log("Trade ID:", result.trade_id);
    console.log("Status:", result.status);
    console.log("Amount spent:", result.currency_amount);
    console.log("Remaining balance:", result.cash_balance);

    const portfolio = await getPortfolio();

    console.log("Updated holdings:", portfolio.holdings);
    console.log("Total portfolio value:", portfolio.total_value);
  } catch (error) {
    console.error("Trading API failed:", error);
    process.exitCode = 1;
  }
}

main();
