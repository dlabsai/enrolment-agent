import { apiGet, apiPost } from "@va/shared/lib/api-client";

import type { UserProfile } from "../types";

interface AuthResponse {
    access_token: string;
    token_type: string;
}

interface LoginPayload {
    email: string;
    password: string;
}

interface RegisterPayload extends LoginPayload {
    name: string;
    confirm_password: string;
    registration_token: string;
}

export const loginUser = async (payload: LoginPayload): Promise<AuthResponse> =>
    apiPost<AuthResponse>("/auth/login", payload, { credentials: "include" });

export const registerUser = async (
    payload: RegisterPayload,
): Promise<AuthResponse> =>
    apiPost<AuthResponse>("/auth/register", payload, {
        credentials: "include",
    });

export const fetchCurrentUser = async (token: string): Promise<UserProfile> =>
    apiGet<UserProfile>("/auth/me", { token });

export const refreshSession = async (): Promise<AuthResponse> =>
    apiPost<AuthResponse>("/auth/refresh", {}, { credentials: "include" });

export const logoutUser = async (): Promise<{ success: boolean }> =>
    apiPost<{ success: boolean }>(
        "/auth/logout",
        {},
        {
            credentials: "include",
        },
    );
