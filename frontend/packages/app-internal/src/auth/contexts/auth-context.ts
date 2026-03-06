import { createContext, use } from "react";

import type { UserProfile } from "../types";

export interface AuthContextValue {
    user?: UserProfile;
    token?: string;
    loading: boolean;
    sessionExpired: boolean;
    markSessionExpired: () => void;
    authenticate: (token: string) => Promise<void>;
    refreshSession: () => Promise<string | undefined>;
    logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(
    undefined,
);

export const useAuth = (): AuthContextValue => {
    const value = use(AuthContext);
    if (value === undefined) {
        throw new Error("useAuth must be used within AuthProvider");
    }
    return value;
};
