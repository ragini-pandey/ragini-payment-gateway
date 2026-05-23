import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiClient,
  type DeliveryListResponse,
  type DeliveryStatus,
  type EventType,
  type Webhook,
} from "@/lib/apiClient";

export interface DeliveryLogParams {
  limit?: number;
  offset?: number;
  status?: DeliveryStatus;
}

export function useDeliveryLogs(
  webhookId: string | null,
  params: DeliveryLogParams = {}
) {
  const qc = useQueryClient();
  const queryKey = [
    "deliveries",
    webhookId,
    params.limit ?? 25,
    params.offset ?? 0,
    params.status ?? "all",
  ] as const;
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["deliveries", webhookId] });

  const list = useQuery<DeliveryListResponse>({
    queryKey,
    queryFn: () =>
      apiClient.listDeliveries(webhookId!, {
        limit: params.limit ?? 25,
        offset: params.offset ?? 0,
        status: params.status,
      }),
    enabled: !!webhookId,
  });

  const sendTest = useMutation<
    { eventId: string; queued: boolean },
    Error,
    { eventType?: EventType; data?: Record<string, unknown> }
  >({
    mutationFn: (opts) => apiClient.sendTestEvent(webhookId!, opts),
    onSuccess: invalidate,
  });

  const retry = useMutation<{ deliveryId: string; queued: boolean }, Error, string>({
    mutationFn: (deliveryId) => apiClient.retryDelivery(deliveryId),
    onSuccess: invalidate,
  });

  const rotateSecret = useMutation<Webhook, Error, void>({
    mutationFn: () => apiClient.rotateWebhookSecret(webhookId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    },
  });

  return { list, sendTest, retry, rotateSecret };
}
