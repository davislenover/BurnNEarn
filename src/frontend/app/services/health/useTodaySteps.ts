import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { getTodaysSteps } from "./steps";

/**
 * Reads steps on mount and when the app returns to the foreground.
 * Pass false until the health notice is acknowledged, or while the screen is hidden.
 */
export function useTodaySteps(enabled = true) {
    const [steps, setSteps] = useState<number | null>(null);
    const [loading, setLoading] = useState(enabled);
    const [error, setError] = useState<Error | null>(null);
    const refreshRef = useRef<() => Promise<void>>(async () => {});

    // Keep one stable refresh function for buttons and other UI callers.
    const refresh = useCallback(() => refreshRef.current(), []);

    useEffect(() => {
        if (!enabled) {
            setSteps(null);
            setLoading(false);
            setError(null);
            return;
        }

        let cancelled = false;
        let pending: Promise<void> | null = null;

        async function readSteps() {
            setLoading(true);
            setError(null);
            try {
                const total = await getTodaysSteps();
                if (!cancelled) {
                    setSteps(total);
                }
            } catch (cause) {
                if (!cancelled) {
                    // Do not leave an old count displayed as current after a failed read.
                    setSteps(null);
                    setError(cause instanceof Error ? cause : new Error("Could not read today's steps."));
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        function refreshSteps(): Promise<void> {
            // Returning to the app during a permission prompt must not start another read.
            if (!pending) {
                pending = readSteps().finally(() => {
                    pending = null;
                });
            }
            return pending;
        }

        refreshRef.current = refreshSteps;
        let previousState = AppState.currentState;

        const subscription = AppState.addEventListener("change", nextState => {
            if (nextState === "active" && previousState !== "active") {
                void refreshSteps();
            }
            previousState = nextState;
        });

        void refreshSteps();

        return () => {
            cancelled = true;
            refreshRef.current = async () => {};
            subscription.remove();
        };
    }, [enabled]);

    return { steps, loading, error, refresh };
}
