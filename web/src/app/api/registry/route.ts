import { proxyApi } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  return proxyApi("/registry", request);
}

export async function POST(request: Request) {
  return proxyApi("/registry", request);
}
