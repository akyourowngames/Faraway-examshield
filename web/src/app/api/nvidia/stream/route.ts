export const runtime = "nodejs";

const NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1";

export async function POST(request: Request) {
  const apiKey = process.env.NVIDIA_API_KEY?.trim();
  if (!apiKey) {
    return Response.json(
      { error: "NVIDIA_API_KEY is not configured." },
      { status: 503 },
    );
  }

  const body = await request.json();

  const upstream = await fetch(`${NVIDIA_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: body.model || "qwen/qwen3-next-80b-a3b-instruct",
      messages: body.messages,
      stream: true,
      max_tokens: body.max_tokens ?? 180,
      temperature: body.temperature ?? 0,
      top_p: body.top_p ?? 0.7,
    }),
  });

  if (!upstream.ok) {
    const text = await upstream.text();
    return Response.json(
      { error: `NVIDIA API error: ${upstream.status} ${text}` },
      { status: upstream.status },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
