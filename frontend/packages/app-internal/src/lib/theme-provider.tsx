import {
    type JSX,
    type ReactNode,
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import { type ResolvedTheme, type Theme, ThemeContext } from "./theme-context";

const getSystemTheme = (): ResolvedTheme =>
    window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";

const isTheme = (value?: string): value is Theme =>
    value === "dark" || value === "light" || value === "system";

export const ThemeProvider = ({
    children,
    defaultTheme = "system",
    storageKey = "theme",
}: {
    children: ReactNode;
    defaultTheme?: Theme;
    storageKey?: string;
}): JSX.Element => {
    const [theme, setTheme] = useState(() => {
        const stored = window.localStorage.getItem(storageKey) ?? undefined;
        return isTheme(stored) ? stored : defaultTheme;
    });

    const resolvedTheme = useMemo(() => {
        if (theme === "system") {
            return getSystemTheme();
        }
        return theme;
    }, [theme]);

    useEffect(() => {
        const root = window.document.documentElement;
        root.classList.remove("light", "dark");
        root.classList.add(resolvedTheme);
    }, [resolvedTheme]);

    const handleSetTheme = useCallback(
        (value: Theme) => {
            window.localStorage.setItem(storageKey, value);
            setTheme(value);
        },
        [storageKey],
    );

    const value = useMemo(
        () => ({ theme, resolvedTheme, setTheme: handleSetTheme }),
        [theme, resolvedTheme, handleSetTheme],
    );

    return <ThemeContext value={value}>{children}</ThemeContext>;
};
