const RETRYABLE_STATUSES = new Set([408, 429, 502, 503, 504]);

function getApiUrl() {
  const value = process.env.EXAMSHIELD_API_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

function getTimeoutMs() {
  const parsed = Number(process.env.EXAMSHIELD_API_TIMEOUT_MS || "28000");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 28000;
}

function getRetries() {
  const parsed = Number(process.env.EXAMSHIELD_API_RETRIES || "2");
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 2;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

async function fetchUpstream(url: string, init: RequestInit, retries = getRetries()) {
  let lastError: unknown = null;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), getTimeoutMs());

    try {
      const response = await fetch(url, {
        ...init,
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (RETRYABLE_STATUSES.has(response.status) && attempt < retries) {
        await sleep(600 * (attempt + 1));
        continue;
      }

      return response;
    } catch (error) {
      clearTimeout(timeout);
      lastError = error;
      if (attempt < retries) {
        await sleep(700 * (attempt + 1));
        continue;
      }
    }
  }

  throw lastError instanceof Error ? lastError : new Error("Upstream request failed.");
}

function buildProxyResponse(upstream: Response) {
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  const cacheControl = upstream.headers.get("cache-control");
  const connection = upstream.headers.get("connection");
  const accelBuffering = upstream.headers.get("x-accel-buffering");

  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (cacheControl) {
    headers.set("cache-control", cacheControl);
  }
  if (connection) {
    headers.set("connection", connection);
  }
  if (accelBuffering) {
    headers.set("x-accel-buffering", accelBuffering);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  });
}

export async function proxyApi(path: string, request?: Request) {
  const apiUrl = getApiUrl();
  if (!apiUrl) {
    return Response.json(
      { error: "EXAMSHIELD_API_URL is not configured on the frontend host." },
      { status: 503 },
    );
  }

  const method = request?.method ?? "GET";
  let body: ArrayBuffer | undefined;
  if (method !== "GET" && method !== "HEAD" && request) {
    try {
      body = await request.arrayBuffer();
    } catch {
      body = undefined;
    }
  }

  try {
    const upstream = await fetchUpstream(`${apiUrl}${path}`, {
      method,
      headers: getForwardHeaders(request),
      body,
      cache: "no-store",
    });

    return buildProxyResponse(upstream);
  } catch (error) {
    return Response.json(
      { error: `Backend unreachable: ${error instanceof Error ? error.message : "unknown"}` },
      { status: 502 },
    );
  }
}

export async function proxyStreamApi(path: string, request: Request) {
  const apiUrl = getApiUrl();
  if (!apiUrl) {
    return Response.json(
      { error: "EXAMSHIELD_API_URL is not configured on the frontend host." },
      { status: 503 },
    );
  }

  let body: ArrayBuffer;
  try {
    body = await request.arrayBuffer();
  } catch {
    body = new ArrayBuffer(0);
  }

  try {
    const upstream = await fetchUpstream(`${apiUrl}${path}`, {
      method: request.method,
      headers: getForwardHeaders(request),
      body,
      cache: "no-store",
    });

    if (!upstream.ok) {
      const text = await upstream.text();
      return Response.json(
        { error: text || `Upstream error ${upstream.status}` },
        { status: upstream.status },
      );
    }

    return buildProxyResponse(upstream);
  } catch (error) {
    return Response.json(
      { error: `Backend unreachable: ${error instanceof Error ? error.message : "unknown"}` },
      { status: 502 },
    );
  }
}
