export async function proxyApi(path: string, request?: Request) {
  const apiUrl = getApiUrl();
  if (!apiUrl) {
    return Response.json(
      { error: "EXAMSHIELD_API_URL is not configured on the frontend host." },
      { status: 503 },
    );
  }

  const upstream = await fetch(`${apiUrl}${path}`, {
    method: request?.method ?? "GET",
    headers: getForwardHeaders(request),
    body: request ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  const cacheControl = upstream.headers.get("cache-control");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (cacheControl) {
    headers.set("cache-control", cacheControl);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  });
}

function getApiUrl() {
  const value = process.env.EXAMSHIELD_API_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

function getForwardHeaders(request?: Request) {
  const headers = new Headers();
  const contentType = request?.headers.get("content-type");
  const authorization = request?.headers.get("authorization");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (authorization) {
    headers.set("authorization", authorization);
  }
  return headers;
}
