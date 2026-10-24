const backendUrl = (
  process.env.GLUCOSE_TWIN_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export async function proxyBackendRequest(path, request = null) {
  try {
    const method = (request?.method || "GET").toUpperCase();

    const headers = {
      Accept: "application/json",
    };

    const contentType = request?.headers.get("content-type");

    if (contentType) {
      headers["Content-Type"] = contentType;
    }

    const options = {
      method,
      cache: "no-store",
      headers,
    };

    if (request && !["GET", "HEAD"].includes(method)) {
      options.body = await request.text();
    }

    const response = await fetch(`${backendUrl}${path}`, options);

    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    console.error("FastAPI backend request failed:", error);

    return Response.json(
      {
        detail:
          "Unable to reach the FastAPI backend. Check GLUCOSE_TWIN_API_URL and the server status.",
      },
      { status: 502 },
    );
  }
}
