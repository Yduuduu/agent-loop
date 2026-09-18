import { create } from "zustand";

import type {
  AwaitingHumanData,
  DecisionData,
  ErrorData,
  NodeEndData,
  NodeStartData,
  ToolCallData,
} from "@/lib/types";

export type ConnectionStatus = "idle" | "connecting" | "open" | "closed" | "unavailable";

export interface ToolCallLogEntry {
  node: string;
  summary: string;
  at: number;
}

interface RefundStreamState {
  caseId: string | null;
  connectionStatus: ConnectionStatus;
  currentNode: string | null;
  /** 오류 발생 시점에 실행 중이던 노드 — 어느 단계에서 실패했는지 보여주는 용도. */
  failedNode: string | null;
  completedNodes: string[];
  toolCallLog: ToolCallLogEntry[];
  latestDecision: DecisionData | null;
  awaitingHuman: AwaitingHumanData | null;
  errorMessage: string | null;

  /** 새 스트림 연결을 시작할 때 호출 — 이전 연결의 잔여 상태를 리셋해
   * 재연결/재개 시 오래된 데이터가 섞이지 않게 한다. */
  startStream: (caseId: string) => void;
  handleConnectionOpen: () => void;
  handleConnectionClosed: () => void;
  /** 스트림 큐가 이미 소비됐거나(410) 시작된 적 없어 재연결이 불가능한 경우. */
  handleConnectionUnavailable: () => void;
  handleNodeStart: (data: NodeStartData) => void;
  handleNodeEnd: (data: NodeEndData) => void;
  handleToolCall: (data: ToolCallData) => void;
  handleDecision: (data: DecisionData) => void;
  handleAwaitingHuman: (data: AwaitingHumanData) => void;
  handleErrorEvent: (data: ErrorData) => void;
}

function addCompletedNode(nodes: string[], node: string): string[] {
  return nodes.includes(node) ? nodes : [...nodes, node];
}

function addToolCallLogEntry(log: ToolCallLogEntry[], entry: ToolCallLogEntry): ToolCallLogEntry[] {
  const isDuplicate = log.some((e) => e.node === entry.node && e.summary === entry.summary);
  return isDuplicate ? log : [...log, entry];
}

export const useRefundStreamStore = create<RefundStreamState>((set) => ({
  caseId: null,
  connectionStatus: "idle",
  currentNode: null,
  failedNode: null,
  completedNodes: [],
  toolCallLog: [],
  latestDecision: null,
  awaitingHuman: null,
  errorMessage: null,

  startStream: (caseId) =>
    set({
      caseId,
      connectionStatus: "connecting",
      currentNode: null,
      failedNode: null,
      completedNodes: [],
      toolCallLog: [],
      latestDecision: null,
      awaitingHuman: null,
      errorMessage: null,
    }),

  handleConnectionOpen: () => set({ connectionStatus: "open" }),
  handleConnectionClosed: () => set({ connectionStatus: "closed" }),
  handleConnectionUnavailable: () =>
    set((state) => (state.connectionStatus === "open" ? state : { connectionStatus: "unavailable" })),

  handleNodeStart: (data) =>
    set((state) => (state.caseId === data.case_id ? { currentNode: data.node } : state)),

  handleNodeEnd: (data) =>
    set((state) =>
      state.caseId === data.case_id
        ? {
            completedNodes: addCompletedNode(state.completedNodes, data.node),
            currentNode: state.currentNode === data.node ? null : state.currentNode,
          }
        : state,
    ),

  handleToolCall: (data) =>
    set((state) =>
      state.caseId === data.case_id
        ? {
            completedNodes: addCompletedNode(state.completedNodes, data.node),
            toolCallLog: addToolCallLogEntry(state.toolCallLog, {
              node: data.node,
              summary: data.summary,
              at: Date.now(),
            }),
            currentNode: state.currentNode === data.node ? null : state.currentNode,
          }
        : state,
    ),

  handleDecision: (data) =>
    set((state) =>
      state.caseId === data.case_id ? { latestDecision: data, currentNode: null } : state,
    ),

  handleAwaitingHuman: (data) =>
    set((state) =>
      state.caseId === data.case_id ? { awaitingHuman: data, currentNode: null } : state,
    ),

  handleErrorEvent: (data) =>
    set((state) =>
      state.caseId === data.case_id
        ? { errorMessage: data.message, failedNode: state.currentNode, currentNode: null }
        : state,
    ),
}));
