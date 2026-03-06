import { logger } from "@va/shared/lib/logger";
import {
    type JSX,
    type ReactNode,
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    fetchCurrentUser,
    logoutUser,
    refreshSession as refreshSessionApi,
} from "../lib/api";
import {
    clearStoredToken,
    getStoredToken,
    setStoredToken,
} from "../lib/storage";
import type { UserProfile } from "../types";
import { AuthContext, type AuthContextValue } from "./auth-context";

const fetchAndStoreUser = async (
    token: string,
    setUser: (user?: UserProfile) => void,
): Promise<void> => {
    const profile = await fetchCurrentUser(token);
    setUser(profile);
};

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps): JSX.Element => {
    const [token, setToken] = useState(() => getStoredToken());
    const [user, setUser] = useState<UserProfile | undefined>();
    const [loading, setLoading] = useState(true);
    const [sessionExpired, setSessionExpired] = useState(false);

    const refreshSessionToken = useCallback(async (): Promise<
        string | undefined
    > => {
        try {
            const response = await refreshSessionApi();
            const newToken = response.access_token;
            await fetchAndStoreUser(newToken, setUser);
            setStoredToken(newToken);
            setToken(newToken);
            setSessionExpired(false);
            return newToken;
        } catch (error) {
            logger.warn("Failed to refresh session", error);
            clearStoredToken();
            setToken(undefined);
            setUser(undefined);
            return undefined;
        }
    }, []);

    useEffect(() => {
        const initialize = async (): Promise<void> => {
            if (token === undefined) {
                await refreshSessionToken();
                setLoading(false);
                return;
            }

            try {
                await fetchAndStoreUser(token, setUser);
            } catch (error) {
                logger.warn("Failed to restore session", error);
                await refreshSessionToken();
            } finally {
                setLoading(false);
            }
        };

        void initialize();
    }, [token, refreshSessionToken]);

    const markSessionExpired = useCallback(() => {
        clearStoredToken();
        setToken(undefined);
        setUser(undefined);
        setSessionExpired(true);
    }, []);

    const authenticate = useCallback(async (nextToken: string) => {
        await fetchAndStoreUser(nextToken, setUser);
        setStoredToken(nextToken);
        setToken(nextToken);
        setSessionExpired(false);
    }, []);

    const logout = useCallback(() => {
        void logoutUser();
        clearStoredToken();
        setToken(undefined);
        setUser(undefined);
        setSessionExpired(false);
    }, []);

    const value = useMemo<AuthContextValue>(
        () => ({
            user,
            token,
            loading,
            sessionExpired,
            markSessionExpired,
            authenticate,
            refreshSession: refreshSessionToken,
            logout,
        }),
        [
            user,
            token,
            loading,
            sessionExpired,
            markSessionExpired,
            authenticate,
            refreshSessionToken,
            logout,
        ],
    );

    return <AuthContext value={value}>{children}</AuthContext>;
};
