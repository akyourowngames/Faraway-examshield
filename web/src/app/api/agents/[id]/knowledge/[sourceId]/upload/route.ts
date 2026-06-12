import { proxyApi } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; sourceId: string }> }
) {
  const { id, sourceId } = await params;
  return proxyApi(
    `/agents/${encodeURIComponent(id)}/knowledge/${encodeURIComponent(sourceId)}/upload`,
    request
  );
}
