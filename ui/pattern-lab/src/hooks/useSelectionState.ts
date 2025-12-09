import { useCallback } from "react";
import { useAppStore } from "../store/useAppStore";
import { Candle } from "../types/domain";

export const useSelectionState = () => {
  const { candidateWindow, setCandidateWindow } = useAppStore();

  const startSelection = useCallback(
    (candle: Candle) => {
      setCandidateWindow({ start_ts: candle.timestamp, end_ts: candle.timestamp });
    },
    [setCandidateWindow],
  );

  const extendSelection = useCallback(
    (candle: Candle) => {
      if (!candidateWindow) {
        setCandidateWindow({ start_ts: candle.timestamp, end_ts: candle.timestamp });
        return;
      }
      const start = new Date(candidateWindow.start_ts);
      const end = new Date(candidateWindow.end_ts);
      const ts = new Date(candle.timestamp);
      const newStart = ts < start ? ts.toISOString() : candidateWindow.start_ts;
      const newEnd = ts > end ? ts.toISOString() : candidateWindow.end_ts;
      setCandidateWindow({ start_ts: newStart, end_ts: newEnd });
    },
    [candidateWindow, setCandidateWindow],
  );

  const clearSelection = useCallback(() => setCandidateWindow(undefined), [setCandidateWindow]);

  return { candidateWindow, startSelection, extendSelection, clearSelection };
};

