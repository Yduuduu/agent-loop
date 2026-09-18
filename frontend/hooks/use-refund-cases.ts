import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createRefundRequest,
  getRefundRequest,
  listRefundRequests,
  resumeRefundRequest,
} from "@/lib/api-client";
import type { RefundCaseStatus, RefundCaseStatusResponse, RefundResumeRequest } from "@/lib/types";

const TERMINAL_STATUSES: RefundCaseStatus[] = ["completed", "failed"];

/** 케이스 메타데이터(상태 폴링) — SSE 스트리밍 상태(Zustand)와 역할을 분리해,
 * 스트림 연결이 끊겨도 이 훅이 진실의 원천 역할을 한다. */
export function useRefundCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ["refund-case", caseId],
    queryFn: () => getRefundRequest(caseId as string),
    enabled: Boolean(caseId),
    refetchInterval: (query) => {
      const data = query.state.data as RefundCaseStatusResponse | undefined;
      if (!data || TERMINAL_STATUSES.includes(data.status)) return false;
      return 4000;
    },
  });
}

export function useRefundCases(status?: RefundCaseStatus) {
  return useQuery({
    queryKey: ["refund-cases", status ?? "all"],
    queryFn: () => listRefundRequests(status),
    // 대시보드의 awaiting_human 대기열이 새 케이스를 빠르게 반영하도록 가볍게 폴링한다.
    refetchInterval: 8000,
  });
}

export function useCreateRefundRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createRefundRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refund-cases"] });
    },
  });
}

export function useResumeRefundRequest(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RefundResumeRequest) => resumeRefundRequest(caseId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["refund-case", caseId] });
      queryClient.invalidateQueries({ queryKey: ["refund-cases"] });
    },
  });
}
