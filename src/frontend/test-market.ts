
import { getAssets } from "./app/services/api/market";

async function main() {
  try {
    const data = await getAssets();

    console.log("Connected to backend!");
    console.log("Market open:", data.market_open);
    console.log("Assets:", data.assets);
  } catch (error) {
    console.error("Connection failed:", error);
    process.exitCode = 1;
  }
}

main();
