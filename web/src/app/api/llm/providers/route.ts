import { proxyApi } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  return proxyApi("/llm/providers", request);
}
