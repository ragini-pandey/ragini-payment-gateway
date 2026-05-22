import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, type Webhook } from "@/lib/apiClient";
import { useEnvironment } from "@/lib/env";

export function useWebhooks() {
  const qc = useQueryClient();
  const { environment } = useEnvironment();
  const key = ["webhooks", environment] as const;

  const list = useQuery<Webhook[]>({
    queryKey: key,
    queryFn: () => apiClient.listWebhooks(environment),
  });

  const create = useMutation<
    Webhook,
    Error,
    { url: string; description?: string; events: string[] }
  >({
    mutationFn: (input) => apiClient.createWebhook({ ...input, environment }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  const remove = useMutation<void, Error, string>({
    mutationFn: (id) => apiClient.deleteWebhook(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  return { list, create, remove };
}
