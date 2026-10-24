import { proxyBackendRequest } from "@/lib/api/backend";

export const dynamic = "force-dynamic";

export async function POST(request) {
  return proxyBackendRequest("/whatif", request);
}

