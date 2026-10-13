import { proxyBackendRequest } from "@/lib/api/backend";

export async function GET(_request, { params }) {
  const { patientId } = await params;
  return proxyBackendRequest(`/patients/${encodeURIComponent(patientId)}/latest`);
}
