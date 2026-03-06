import { useCallback, useEffect, useRef, useState } from "react";

import {
    type AuthenticatedApi,
    useAuthenticatedApi,
} from "../../auth/hooks/use-authenticated-api";
import type { TraceDetail } from "../types";

interface UseTraceDetailLoaderOptions {
    clearDetailOnError?: boolean;
}

interface UseTraceDetailLoaderResult {
    detail: TraceDetail | undefined;
    loading: boolean;
    error: string | undefined;
    refresh: () => Promise<void>;
}

type TraceDetailFetcher = (
    api: AuthenticatedApi,
    id: string,
) => Promise<TraceDetail>;

export const useTraceDetailLoader = (
    id: string | undefined,
    fetcher: TraceDetailFetcher,
    options: UseTraceDetailLoaderOptions = {},
): UseTraceDetailLoaderResult => {
    const api = useAuthenticatedApi();
    const [detail, setDetail] = useState<TraceDetail | undefined>();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | undefined>();
    const requestIdRef = useRef(0);
    const mountedRef = useRef(true);

    useEffect((): (() => void) => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);

    const refresh = useCallback(async (): Promise<void> => {
        requestIdRef.current += 1;
        const requestId = requestIdRef.current;
        const isActive = (): boolean =>
            mountedRef.current && requestId === requestIdRef.current;

        if (id === undefined || id.trim() === "") {
            if (isActive()) {
                setDetail(undefined);
                setError(undefined);
                setLoading(false);
            }
            return;
        }

        if (isActive()) {
            setLoading(true);
            setError(undefined);
        }

        try {
            const data = await fetcher(api, id);
            if (!isActive()) {
                return;
            }
            setDetail(data);
        } catch (error_) {
            if (!isActive()) {
                return;
            }
            setError(
                error_ instanceof Error
                    ? error_.message
                    : "Failed to fetch trace",
            );
            if (options.clearDetailOnError === true) {
                setDetail(undefined);
            }
        } finally {
            if (isActive()) {
                setLoading(false);
            }
        }
    }, [api, fetcher, id, options.clearDetailOnError]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    return { detail, loading, error, refresh };
};
