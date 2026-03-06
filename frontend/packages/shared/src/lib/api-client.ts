import { API_URL } from "../config";
import { logger } from "./logger";
import { isRecord } from "./type-guards";

export interface ApiClientOptions {
    token?: string;
    signal?: AbortSignal;
    headers?: Record<string, string>;
    baseUrl?: string;
    credentials?: RequestCredentials;
}

interface ApiError extends Error {
    status: number;
    detail: string;
}

export const isApiError = (error: unknown): error is ApiError => {
    if (!(error instanceof Error)) {
        return false;
    }
    if (!("status" in error) || typeof error.status !== "number") {
        return false;
    }
    if (!("detail" in error) || typeof error.detail !== "string") {
        return false;
    }
    return true;
};

const createApiError = (status: number, detail: string): ApiError =>
    Object.assign(new Error(`${String(status)}: ${detail}`), {
        status,
        detail,
    });

const parseErrorResponse = async (response: Response): Promise<string> => {
    try {
        const data: unknown = await response.json();
        if (isRecord(data) && typeof data.detail === "string") {
            return data.detail;
        }
        return "Request failed";
    } catch {
        return "Request failed";
    }
};

const buildHeaders = (
    options: ApiClientOptions = {},
): Record<string, string> => {
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...options.headers,
    };

    if (options.token !== undefined && options.token !== "") {
        headers.Authorization = `Bearer ${options.token}`;
    }

    return headers;
};

const apiFetch = async <T>(
    endpoint: string,
    options: ApiClientOptions,
    fetchOptions: RequestInit,
): Promise<T | undefined> => {
    const baseUrl = options.baseUrl ?? API_URL;
    const url = `${baseUrl}${endpoint}`;

    const response = await fetch(url, {
        ...fetchOptions,
        headers: buildHeaders(options),
        signal: options.signal,
        credentials: options.credentials,
    });

    if (!response.ok) {
        const detail = await parseErrorResponse(response);
        throw createApiError(response.status, detail);
    }

    if (response.status === 204) {
        // No content to parse.
        return undefined;
    }

    // `response.json()` is typed as `any`; keep the unsafety local to the client.
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const data: T = await response.json();
    return data;
};

export const apiGet = async <T>(
    endpoint: string,
    options: ApiClientOptions = {},
): Promise<T> => {
    const result = await apiFetch<T>(endpoint, options, { method: "GET" });
    if (result === undefined) {
        throw new Error("Unexpected empty response");
    }
    return result;
};

export const apiPost = async <T>(
    endpoint: string,
    body: unknown,
    options: ApiClientOptions = {},
): Promise<T> => {
    const result = await apiFetch<T>(endpoint, options, {
        method: "POST",
        body: JSON.stringify(body),
    });
    if (result === undefined) {
        throw new Error("Unexpected empty response");
    }
    return result;
};

export const apiPostStream = async (
    endpoint: string,
    body: unknown,
    options: ApiClientOptions = {},
): Promise<Response> => {
    const baseUrl = options.baseUrl ?? API_URL;
    const url = `${baseUrl}${endpoint}`;

    const headers = buildHeaders(options);
    headers.Accept = "text/event-stream";

    const response = await fetch(url, {
        method: "POST",
        body: JSON.stringify(body),
        headers,
        signal: options.signal,
        credentials: options.credentials,
    });

    if (!response.ok) {
        const detail = await parseErrorResponse(response);
        throw createApiError(response.status, detail);
    }

    return response;
};

export const apiPut = async <T>(
    endpoint: string,
    body: unknown,
    options: ApiClientOptions = {},
): Promise<T> => {
    const result = await apiFetch<T>(endpoint, options, {
        method: "PUT",
        body: JSON.stringify(body),
    });
    if (result === undefined) {
        throw new Error("Unexpected empty response");
    }
    return result;
};

export const apiDelete = async (
    endpoint: string,
    options: ApiClientOptions = {},
): Promise<void> => {
    await apiFetch<unknown>(endpoint, options, { method: "DELETE" });
};

export const handleFetchError = (error: unknown, context: string): string => {
    if (error instanceof DOMException && error.name === "AbortError") {
        logger.log(`${context}: Request aborted`);
        return "Request was cancelled";
    }

    logger.error(`${context}:`, error);

    if (error instanceof Error) {
        return error.message;
    }

    return "An unexpected error occurred";
};

export const isAbortError = (error: unknown): boolean =>
    error instanceof DOMException && error.name === "AbortError";
