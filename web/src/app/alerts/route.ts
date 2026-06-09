import { proxyApi } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET() {
  return proxyApi("/alerts");
}
