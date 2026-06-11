export const runtime = "nodejs";

/** @deprecated Use POST /api/chat — NVIDIA keys stay on Render only. */
export async function POST() {
  return Response.json(
    { error: "This route is deprecated. Use POST /api/chat instead." },
    { status: 410 },
  );
}
