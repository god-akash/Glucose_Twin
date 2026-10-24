import { proxyBackendRequest } from "../../../lib/api/backend";

export const dynamic = "force-dynamic";

export function POST(request) {
  return proxyBackendRequest("/explain", request);
} 