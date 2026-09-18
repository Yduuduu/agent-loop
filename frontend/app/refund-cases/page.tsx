"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useCreateRefundRequest } from "@/hooks/use-refund-cases";

export default function NewRefundCasePage() {
  const router = useRouter();
  const [orderId, setOrderId] = useState("ORD-1001");
  const [message, setMessage] = useState("제품이 파손된 상태로 도착했습니다.");
  const createRequest = useCreateRefundRequest();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const result = await createRequest.mutateAsync({ orderId, message });
    router.push(`/refund-cases/${result.case_id}`);
  };

  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-xl font-semibold">환불 요청 제출 (수동 테스트용)</h1>
        <p className="mt-1 text-sm text-text-secondary">
          backend/data/mock_orders.json의 order_id를 사용해 시나리오를 테스트할 수 있습니다.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">주문 ID</span>
          <input
            className="rounded-md border border-border-subtle bg-transparent px-3 py-2"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">고객 메시지</span>
          <textarea
            className="min-h-24 rounded-md border border-border-subtle bg-transparent px-3 py-2"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            required
          />
        </label>

        <button
          type="submit"
          disabled={createRequest.isPending}
          className="rounded-md bg-status-progress px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {createRequest.isPending ? "제출 중..." : "환불 요청 제출"}
        </button>

        {createRequest.isError && (
          <p className="text-sm text-status-critical">
            제출에 실패했습니다: {String(createRequest.error)}
          </p>
        )}
      </form>
    </div>
  );
}
