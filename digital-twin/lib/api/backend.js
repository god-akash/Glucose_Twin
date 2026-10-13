const backendUrl = (process.env.GLUCOSE_TWIN_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export async function proxyBackendRequest(path) {
  try {
    const response = await fetch(`${backendUrl}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    console.error("FastAPI backend request failed:", error);
    return Response.json(
      { detail: "Unable to reach the FastAPI backend. Check GLUCOSE_TWIN_API_URL and the server status." },
      { status: 502 },
    );
  }
}
