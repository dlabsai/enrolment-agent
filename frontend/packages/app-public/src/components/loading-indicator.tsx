import { DEFAULT_LOADING_MESSAGES } from "@va/shared/components/loading-messages";
import type { LoadingIndicatorProps } from "@va/shared/types";
import { type JSX, useEffect, useRef, useState } from "react";

const INITIAL_DELAY = 7000;
const FADE_DURATION = 700;
const VISIBLE_DURATION = 15_000;

export const LoadingIndicator = ({
    isVisible,
    onTextShow,
    messages,
    activityItems,
    activityLog,
    variant = "default",
    showHeader,
    forceOpenReasoning,
    showEmptyState,
}: LoadingIndicatorProps): JSX.Element | undefined => {
    void activityItems;
    void activityLog;
    void showHeader;
    void forceOpenReasoning;
    void showEmptyState;
    void variant;
    void variant;

    const resolvedMessages = messages ?? DEFAULT_LOADING_MESSAGES;
    const hasMessages = resolvedMessages.length > 0;

    const [messageIndex, setMessageIndex] = useState(0);
    const currentMessage =
        resolvedMessages[messageIndex] ?? resolvedMessages[0];
    const [showMessage, setShowMessage] = useState(false);
    const [isTextVisible, setIsTextVisible] = useState(false);
    const onTextShowRef = useRef(onTextShow);

    useEffect(() => {
        onTextShowRef.current = onTextShow;
    }, [onTextShow]);

    const [prevIsVisible, setPrevIsVisible] = useState(isVisible);
    if (prevIsVisible !== isVisible) {
        setPrevIsVisible(isVisible);
        if (!isVisible) {
            setMessageIndex(0);
            setShowMessage(false);
            setIsTextVisible(false);
        }
    }

    useEffect(() => {
        if (!isVisible || !hasMessages) {
            return (): void => undefined;
        }

        const initialTimer = setTimeout((): void => {
            setShowMessage(true);
            requestAnimationFrame((): void => {
                setIsTextVisible(true);
            });
            onTextShowRef.current?.();
        }, INITIAL_DELAY);

        const cycleDuration = FADE_DURATION + VISIBLE_DURATION + FADE_DURATION;

        const intervalTimer = setInterval((): void => {
            setIsTextVisible(false);

            setTimeout((): void => {
                setMessageIndex((prev) => (prev + 1) % resolvedMessages.length);
                setIsTextVisible(true);
                onTextShowRef.current?.();
            }, FADE_DURATION);
        }, cycleDuration);

        return (): void => {
            clearTimeout(initialTimer);
            clearInterval(intervalTimer);
        };
    }, [hasMessages, isVisible, resolvedMessages.length]);

    if (!isVisible) {
        return undefined;
    }

    return (
        <span className="text-primary flex items-start gap-3 p-3 text-base">
            <div className="bg-primary mt-1 h-[1em] w-[1em] flex-shrink-0 animate-pulse rounded-full" />
            <span className="inline-block min-h-[3rem]">
                {showMessage && hasMessages && (
                    <span
                        className="transition-opacity ease-in-out"
                        style={{
                            opacity: isTextVisible ? 1 : 0,
                            transitionDuration: `${String(FADE_DURATION)}ms`,
                        }}
                    >
                        {currentMessage}
                    </span>
                )}
            </span>
        </span>
    );
};
