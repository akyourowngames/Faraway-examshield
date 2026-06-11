export const runtime = "nodejs";

export async function GET(request: Request) {
  const apiUrl = process.env.EXAMSHIELD_API_URL?.trim().replace(/\/$/, "");
  if (!apiUrl) {
    return Response.json({ ok: false, reason: "EXAMSHIELD_API_URL is not configured." }, { status: 503 });
  }

  const cronSecret = process.env.CRON_SECRET?.trim();
  if (cronSecret) {
    const auth = request.headers.get("authorization");
    if (auth !== `Bearer ${cronSecret}`) {
      return Response.json({ ok: false, reason: "Unauthorized." }, { status: 401 });
    }
  }

  try {
    const upstream = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    const payload = await upstream.json().catch(() => ({}));
    return Response.json({
      ok: upstream.ok,
      status: upstream.status,
      upstream: payload,
      warmedAt: new Date().toISOString(),
    });
  } catch (error) {
    return Response.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "Warmup failed.",
      },
      { status: 503 },
    );
  }
}
