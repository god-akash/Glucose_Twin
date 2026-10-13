import { proxyBackendRequest } from "@/lib/api/backend";

export function GET() {
  return proxyBackendRequest("/patients");
}
