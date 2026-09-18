import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HitlPanel } from "./hitl-panel";

function renderPanel(onResumed: () => void = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <HitlPanel
        caseId="case-1"
        flaggedReason="환불 금액이 고액 기준을 초과했습니다."
        refundAmount={650}
        onResumed={onResumed}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ case_id: "case-1" }),
    })),
  );
});

describe("HitlPanel", () => {
  it("shows the flagged reason and refund amount", () => {
    renderPanel();
    expect(screen.getByText("환불 금액이 고액 기준을 초과했습니다.")).toBeInTheDocument();
    expect(screen.getByText("환불 금액: $650.00")).toBeInTheDocument();
  });

  it("approves immediately without a confirmation step", async () => {
    const user = userEvent.setup();
    const onResumed = vi.fn();
    renderPanel(onResumed);

    await user.click(screen.getByRole("button", { name: "승인" }));

    await waitFor(() => expect(onResumed).toHaveBeenCalled());
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(options!.body as string)).toEqual({ action: "approve", admin_note: null });
  });

  it("requires confirmation before rejecting, and does nothing on cancel", async () => {
    const user = userEvent.setup();
    const onResumed = vi.fn();
    renderPanel(onResumed);

    await user.click(screen.getByRole("button", { name: "거절" }));
    expect(screen.getByText(/정말 이 환불 요청을 거절하시겠습니까/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "취소" }));
    expect(screen.queryByText(/정말 이 환불 요청을 거절하시겠습니까/)).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    expect(onResumed).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "거절" }));
    await user.click(screen.getByRole("button", { name: "거절 확정" }));

    await waitFor(() => expect(onResumed).toHaveBeenCalled());
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(options!.body as string)).toEqual({ action: "reject", admin_note: null });
  });

  it("disables the takeover button until a message is entered, and requires confirmation", async () => {
    const user = userEvent.setup();
    const onResumed = vi.fn();
    renderPanel(onResumed);

    const takeoverButton = screen.getByRole("button", { name: "직접 개입으로 처리" });
    expect(takeoverButton).toBeDisabled();

    const textarea = screen.getByPlaceholderText(/고객과 직접 협의해/);
    await user.type(textarea, "고객과 협의해 부분 환불로 처리함");
    expect(takeoverButton).toBeEnabled();

    await user.click(takeoverButton);
    await user.click(screen.getByRole("button", { name: "직접 개입 확정" }));

    await waitFor(() => expect(onResumed).toHaveBeenCalled());
    const [, options] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(options!.body as string)).toEqual({
      action: "takeover",
      admin_message: "고객과 협의해 부분 환불로 처리함",
    });
  });
});
