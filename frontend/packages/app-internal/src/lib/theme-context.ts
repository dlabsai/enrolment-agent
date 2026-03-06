import { createContext, use } from "react";

export type Theme = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

interface ThemeContextValue {
    theme: Theme;
    resolvedTheme: ResolvedTheme;
    setTheme: (value: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(
    undefined,
);

export const useTheme = (): ThemeContextValue => {
    const value = use(ThemeContext);
    if (!value) {
        throw new Error("useTheme must be used within ThemeProvider.");
    }
    return value;
};
