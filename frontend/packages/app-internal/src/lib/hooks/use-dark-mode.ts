import { useTheme } from "../theme-context";

export const useDarkMode = (): boolean => {
    const { resolvedTheme } = useTheme();
    return resolvedTheme === "dark";
};
