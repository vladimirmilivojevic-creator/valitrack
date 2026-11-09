import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { errorMessage } from "./api";

type Notify = (message: string, tone?: "ok" | "error") => void;

const ToastContext = createContext<Notify>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; message: string; tone: "ok" | "error" }[]>([]);

  const notify = useCallback<Notify>((message, tone = "ok") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => setItems((current) => current.filter((i) => i.id !== id)), tone === "error" ? 7000 : 3500);
  }, []);

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((item) => (
          <div key={item.id} className={`toast ${item.tone === "error" ? "toast--error" : ""}`}>
            {item.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = (): Notify => useContext(ToastContext);

/**
 * Run an API call, show the result as a message and refresh the data on the screen.
 * The error is shown and also thrown again, so a dialog can stay open and show it too.
 */
export function useAct() {
  const notify = useToast();
  const queryClient = useQueryClient();
  return useCallback(
    async <T,>(call: () => Promise<T>, success?: string): Promise<T> => {
      try {
        const result = await call();
        if (success) notify(success);
        await queryClient.invalidateQueries();
        return result;
      } catch (error) {
        notify(errorMessage(error), "error");
        throw error;
      }
    },
    [notify, queryClient],
  );
}
