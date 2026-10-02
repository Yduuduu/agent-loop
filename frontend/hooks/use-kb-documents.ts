import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteKbDocument,
  getKbDocument,
  listKbCategories,
  listKbDocuments,
  listKbPolicies,
  uploadKbDocument,
} from "@/lib/api-client";
import type { KBDocumentResponse } from "@/lib/types";

const TERMINAL_STATUSES: KBDocumentResponse["status"][] = ["indexed", "failed"];

export function useKbDocuments() {
  return useQuery({
    queryKey: ["kb-documents"],
    queryFn: listKbDocuments,
    refetchInterval: 8000,
  });
}

export function useKbDocument(docId: string | undefined) {
  return useQuery({
    queryKey: ["kb-document", docId],
    queryFn: () => getKbDocument(docId as string),
    enabled: Boolean(docId),
    refetchInterval: (query) => {
      const data = query.state.data as KBDocumentResponse | undefined;
      if (!data || TERMINAL_STATUSES.includes(data.status)) return false;
      return 3000;
    },
  });
}

export function useUploadKbDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadKbDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kb-documents"] });
    },
  });
}

export function useDeleteKbDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteKbDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kb-documents"] });
      queryClient.invalidateQueries({ queryKey: ["kb-policies"] });
    },
  });
}

export function useKbCategories() {
  return useQuery({
    queryKey: ["kb-categories"],
    queryFn: listKbCategories,
    // 분류 체계는 백엔드 코드 상수라 세션 중에 바뀌지 않는다.
    staleTime: Infinity,
  });
}

export function useKbPolicies() {
  // 정책 요약은 색인(indexed) 이후에 별도로 끝나므로, 업로드 추적기의 indexed 시점
  // 무효화로는 마지막 문서의 요약을 놓친다. 폴링 중인 문서 목록에서 "요약 완료된
  // 문서 집합"을 쿼리 키에 넣어, 그 집합이 바뀔 때마다 정책 목록을 다시 불러온다.
  const { data: documents } = useKbDocuments();
  const summarizedDocIds = (documents ?? [])
    .filter((doc) => doc.policy_summary_status === "done")
    .map((doc) => doc.doc_id)
    .sort()
    .join(",");

  return useQuery({
    queryKey: ["kb-policies", summarizedDocIds],
    queryFn: listKbPolicies,
    // 키가 바뀌는 동안 이전 목록을 유지해 대시보드가 "불러오는 중"으로 깜빡이지 않게 한다.
    placeholderData: keepPreviousData,
  });
}
