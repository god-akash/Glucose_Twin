"use client";

import { useEffect, useState } from "react";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000";

export function usePatientStream(pid) {
  const [history, setHistory] = useState([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!pid) return;
    let ws, timer;
    let stop = false;
    let attempt = 0;
    const open = () => {
      ws = new WebSocket(`${WS_BASE}/ws/${encodeURIComponent(pid)}`);
      ws.onopen = () => { setConnected(true); attempt = 0; };
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.type === "snapshot") setHistory(m.entries);
        else if (m.type === "readings") setHistory((h) => [...h, ...m.entries].slice(-1200));
      };
      ws.onclose = () => {
        setConnected(false);
        if (!stop) timer = setTimeout(open, Math.min(5000, 500 * 2 ** attempt++));
      };
      ws.onerror = () => ws.close();
    };
    setHistory([]);
    open();
    return () => { stop = true; clearTimeout(timer); if (ws) ws.close(); };
  }, [pid]);

  return { history, connected };
}