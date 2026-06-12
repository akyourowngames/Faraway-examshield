const session = new Supabase.ai.Session("gte-small");

function jsonResponse(payload: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return jsonResponse({ error: "Only POST is supported." }, 405);
  }

  const expectedToken =
    Deno.env.get("EXAMSHIELD_EMBED_TOKEN") ||
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ||
    "";
  const authorization = req.headers.get("authorization") || "";
  if (!authorization || (expectedToken && authorization !== `Bearer ${expectedToken}`)) {
    return jsonResponse({ error: "Unauthorized." }, 401);
  }

  let input = "";
  try {
    const body = await req.json();
    input = typeof body.input === "string" ? body.input.trim() : "";
  } catch {
    return jsonResponse({ error: "Invalid JSON body." }, 400);
  }

  if (!input) {
    return jsonResponse({ error: "input is required." }, 400);
  }

  const embedding = await session.run(input.slice(0, 8000), {
    mean_pool: true,
    normalize: true,
  });

  return jsonResponse({ embedding });
});
