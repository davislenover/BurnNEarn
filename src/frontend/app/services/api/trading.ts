
import { apiRequest } from "./client";

import type {
  BuyTradeRequest,
  BuyTradeResponse,
} from "../../types/api";

/**
 * Buys a whole number of shares using virtual currency.
 * The backend validates prices and available balance.
 */
export async function buyShares(
  request: BuyTradeRequest
): Promise<BuyTradeResponse> {
  if (!Number.isSafeInteger(request.quantity) || request.quantity <= 0) {
    throw new Error("Quantity must be a positive whole number.");
  }

  if (!request.request_id || !request.symbol || !request.expected_price) {
    throw new Error("Missing required trade information.");
  }

  return apiRequest<BuyTradeResponse>("/v1/me/trades", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
