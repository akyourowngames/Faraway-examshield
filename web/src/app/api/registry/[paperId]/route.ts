import { proxyApi } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ paperId: string }> }
) {
  const { paperId } = await params;
  return proxyApi(`/registry/${encodeURIComponent(paperId)}`, request);
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ paperId: string }> }
) {
  const { paperId } = await params;
  return proxyApi(`/registry/${encodeURIComponent(paperId)}`, request);
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ paperId: string }> }
) {
  const { paperId } = await params;
  return proxyApi(`/registry/${encodeURIComponent(paperId)}`, request);
}
