import {
    type ApiClientOptions,
    apiDelete,
    apiGet,
    apiPost,
    apiPostStream,
    apiPut,
    isApiError,
} from "@va/shared/lib/api-client";
import { useMemo } from "react";

import { useAuth } from "../contexts/auth-context";

const withSessionExpiry = async <T>(
    operation: (token?: string) => Promise<T>,
    token: string | undefined,
    refreshSession: () => Promise<string | undefined>,
    onExpire: () => void,
): Promise<T> => {
    try {
        return await operation(token);
    } catch (error) {
        if (isApiError(error) && error.status === 401) {
            const refreshedToken = await refreshSession();
            if (refreshedToken !== undefined && refreshedToken !== "") {
                return operation(refreshedToken);
            }
            onExpire();
        }
        throw error;
    }
};

export const useAuthenticatedApi = (): {
    get: <T>(
        endpoint: string,
        options?: Omit<ApiClientOptions, "token">,
    ) => Promise<T>;
    post: <T>(
        endpoint: string,
        body: unknown,
        options?: Omit<ApiClientOptions, "token">,
    ) => Promise<T>;
    postStream: (
        endpoint: string,
        body: unknown,
        options?: Omit<ApiClientOptions, "token">,
    ) => Promise<Response>;
    put: <T>(
        endpoint: string,
        body: unknown,
        options?: Omit<ApiClientOptions, "token">,
    ) => Promise<T>;
    delete: (
        endpoint: string,
        options?: Omit<ApiClientOptions, "token">,
    ) => Promise<void>;
} => {
    const { token, markSessionExpired, refreshSession } = useAuth();

    return useMemo(
        () => ({
            get: async <T>(
                endpoint: string,
                options?: Omit<ApiClientOptions, "token">,
            ) =>
                withSessionExpiry(
                    async (activeToken) =>
                        apiGet<T>(endpoint, { ...options, token: activeToken }),
                    token,
                    refreshSession,
                    markSessionExpired,
                ),

            post: async <T>(
                endpoint: string,
                body: unknown,
                options?: Omit<ApiClientOptions, "token">,
            ) =>
                withSessionExpiry(
                    async (activeToken) =>
                        apiPost<T>(endpoint, body, {
                            ...options,
                            token: activeToken,
                        }),
                    token,
                    refreshSession,
                    markSessionExpired,
                ),

            postStream: async (
                endpoint: string,
                body: unknown,
                options?: Omit<ApiClientOptions, "token">,
            ) =>
                withSessionExpiry(
                    async (activeToken) =>
                        apiPostStream(endpoint, body, {
                            ...options,
                            token: activeToken,
                        }),
                    token,
                    refreshSession,
                    markSessionExpired,
                ),

            put: async <T>(
                endpoint: string,
                body: unknown,
                options?: Omit<ApiClientOptions, "token">,
            ) =>
                withSessionExpiry(
                    async (activeToken) =>
                        apiPut<T>(endpoint, body, {
                            ...options,
                            token: activeToken,
                        }),
                    token,
                    refreshSession,
                    markSessionExpired,
                ),

            delete: async (
                endpoint: string,
                options?: Omit<ApiClientOptions, "token">,
            ) =>
                withSessionExpiry(
                    async (activeToken) =>
                        apiDelete(endpoint, { ...options, token: activeToken }),
                    token,
                    refreshSession,
                    markSessionExpired,
                ),
        }),
        [token, refreshSession, markSessionExpired],
    );
};

export type AuthenticatedApi = ReturnType<typeof useAuthenticatedApi>;
