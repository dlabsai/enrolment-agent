const TOKEN_KEY = "va_auth_token";

export const getStoredToken = (): string | undefined =>
    localStorage.getItem(TOKEN_KEY) ?? undefined;

export const setStoredToken = (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token);
};

export const clearStoredToken = (): void => {
    localStorage.removeItem(TOKEN_KEY);
};
