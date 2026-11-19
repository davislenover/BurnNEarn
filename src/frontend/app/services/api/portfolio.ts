
import { apiRequest } from "./client";

import type { PortfolioResponse } from "../../types/api";

/**
 * Retrieves the demo user's holdings, cash balance,
 * and current portfolio valuation.
 */
export async function getPortfolio(): Promise<PortfolioResponse> {
  return apiRequest<PortfolioResponse>("/v1/me/portfolio");
}
