"use client";

import { useRefundStreamStore } from "@/store/refund-stream-store";

import { labelForNode } from "./node-labels";

const CORE_PIPELINE = [
  "order_lookup",
  "damage_assessment",
  "policy_rag_search",
  "decision",
] as const;
const TERMINAL_NODES = ["finalize", "flag_for_human"] as const;

type StepStatus = "pending" | "in_progress" | "done" | "failed";

function statusFor(
  node: string,
  currentNode: string | null,
  completedNodes: string[],
  failedNode: string | null,
): StepStatus {
  if (failedNode === node) return "failed";
  if (completedNodes.includes(node)) return "done";
  if (currentNode === node) return "in_progress";
  return "pending";
}

const STATUS_DOT_CLASS: Record<StepStatus, string> = {
  pending: "bg-status-pending",
  in_progress: "bg-status-progress animate-pulse",
  done: "bg-status-good",
  failed: "bg-status-critical",
};

export function AgentViewer() {
  const currentNode = useRefundStreamStore((s) => s.currentNode);
  const failedNode = useRefundStreamStore((s) => s.failedNode);
  const completedNodes = useRefundStreamStore((s) => s.completedNodes);
  const toolCallLog = useRefundStreamStore((s) => s.toolCallLog);

  const activeTerminalNode = TERMINAL_NODES.find(
    (node) => node === currentNode || node === failedNode || completedNodes.includes(node),
  );
  const steps: string[] = activeTerminalNode
    ? [...CORE_PIPELINE, activeTerminalNode]
    : [...CORE_PIPELINE];

  return (
    <div className="flex flex-col gap-4" data-testid="agent-viewer">
      <ol className="flex flex-col gap-2">
        {steps.map((node) => {
          const status = statusFor(node, currentNode, completedNodes, failedNode);
          return (
            <li
              key={node}
              className="flex items-center gap-2"
              data-node={node}
              data-status={status}
            >
              <span
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${STATUS_DOT_CLASS[status]}`}
                aria-hidden
              />
              <span
                className={
                  status === "pending"
                    ? "text-text-secondary"
                    : status === "failed"
                      ? "text-status-critical"
                      : "text-foreground"
                }
              >
                {labelForNode(node, status === "done")}
                {status === "failed" && " — 실패"}
              </span>
            </li>
          );
        })}
      </ol>

      {toolCallLog.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-text-secondary">Tool 호출 로그</h3>
          <ul className="mt-1 flex flex-col gap-1 text-sm text-text-secondary">
            {toolCallLog.map((entry, index) => (
              <li key={`${entry.node}-${index}`}>
                <span className="font-mono text-xs">{entry.node}</span> — {entry.summary}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
