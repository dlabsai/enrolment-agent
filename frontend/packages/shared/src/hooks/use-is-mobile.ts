import { useEffect, useState } from "react";

const DEFAULT_MOBILE_BREAKPOINT = 768;

export const useIsMobile = (
    breakpointPx: number = DEFAULT_MOBILE_BREAKPOINT,
): boolean => {
    const [isMobile, setIsMobile] = useState(
        () => window.innerWidth < breakpointPx,
    );

    useEffect((): (() => void) => {
        const mql = window.matchMedia(
            `(max-width: ${String(breakpointPx - 1)}px)`,
        );
        const onChange = (): void => {
            setIsMobile(window.innerWidth < breakpointPx);
        };
        mql.addEventListener("change", onChange);
        return () => {
            mql.removeEventListener("change", onChange);
        };
    }, [breakpointPx]);

    return isMobile;
};
