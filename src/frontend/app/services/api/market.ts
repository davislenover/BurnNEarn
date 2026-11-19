
import { apiRequest } from "./client";
import type { AssetsResponse } from "../../types/api";

export async function getAssets(): Promise<AssetsResponse> {
  return apiRequest<AssetsResponse>("/v1/assets");
}
