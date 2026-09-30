import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteKbDocument,
  getKbDocument,
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

export function useKbPolicies() {
  return useQuery({
    queryKey: ["kb-policies"],
    queryFn: listKbPolicies,
  });
}
