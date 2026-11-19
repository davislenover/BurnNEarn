
import { apiRequest } from "./client";
import type { BalanceResponse } from "../../types/api";

/**
 * Retrieves the demo user's current virtual currency balance.
 */
export async function getBalance(): Promise<BalanceResponse> {
  return apiRequest<BalanceResponse>("/v1/me/balance");
}
