import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, type ApiKey, type ApiKeyWithSecret } from "@/lib/apiClient";
import { useEnvironment } from "@/lib/env";

export function useApiKeys() {
  const qc = useQueryClient();
  const { environment } = useEnvironment();
  const key = ["apiKeys", environment] as const;

  const list = useQuery<ApiKey[]>({
    queryKey: key,
    queryFn: () => apiClient.listApiKeys(environment),
  });

  const create = useMutation<
    ApiKeyWithSecret,
    Error,
    { name: string; expiresAt?: string | null }
  >({
    mutationFn: (input) => apiClient.createApiKey({ ...input, environment }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  const revoke = useMutation<ApiKey, Error, { id: string; reason?: string }>({
    mutationFn: ({ id, reason }) => apiClient.revokeApiKey(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  return { list, create, revoke };
}
