import { proxyStreamApi } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(request: Request) {
  return proxyStreamApi("/chat", request);
}
