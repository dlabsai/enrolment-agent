import { useCallback, useEffect, useRef, useState } from "react";

interface UseTTSOptions {
    preferredVoice: string;
    enabled: boolean;
}

export const useTTS = ({
    preferredVoice,
    enabled,
}: UseTTSOptions): {
    speak: (text: string, messageId: string) => void;
    stop: () => void;
    playingMessageId?: string;
} => {
    const [playingMessageId, setPlayingMessageId] = useState<
        string | undefined
    >();

    const utteranceRef = useRef<SpeechSynthesisUtterance | undefined>(
        undefined,
    );
    const utteranceCleanupRef = useRef<(() => void) | undefined>(undefined);
    const selectedVoiceRef = useRef<SpeechSynthesisVoice | undefined>(
        undefined,
    );

    const stop = useCallback(() => {
        // Cancel can still trigger `end`/`error` events for the previous utterance.
        // Clear refs first and detach listeners so stale events can't clobber the
        // currently-playing message state.
        const cleanup = utteranceCleanupRef.current;
        utteranceRef.current = undefined;
        utteranceCleanupRef.current = undefined;

        if (cleanup) {
            cleanup();
        }

        window.speechSynthesis.cancel();
        setPlayingMessageId(undefined);
    }, []);

    useEffect(() => {
        if (!enabled) {
            return stop;
        }

        const selectVoice = (): void => {
            const voices = window.speechSynthesis.getVoices();
            const voice = voices.find((voice) => voice.name === preferredVoice);
            if (voice) {
                selectedVoiceRef.current = voice;
            }
        };

        selectVoice();

        window.speechSynthesis.addEventListener("voiceschanged", selectVoice);

        return (): void => {
            window.speechSynthesis.removeEventListener(
                "voiceschanged",
                selectVoice,
            );
            stop();
        };
    }, [enabled, preferredVoice, stop]);

    const speak = useCallback(
        (text: string, messageId: string) => {
            if (!enabled) {
                return;
            }

            if (playingMessageId === messageId) {
                stop();
                return;
            }

            stop();

            const cleanText = text.replaceAll(/\s+/gu, " ").trim();
            const utterance = new SpeechSynthesisUtterance(cleanText);

            utterance.volume = 0.9;
            utterance.rate = 1;
            utterance.pitch = 1;
            utterance.lang = "en-US";

            if (selectedVoiceRef.current) {
                utterance.voice = selectedVoiceRef.current;
            } else {
                const voices = window.speechSynthesis.getVoices();
                const fallbackVoice = voices.find(
                    (voice) =>
                        voice.lang === "en-US" && voice.name === preferredVoice,
                );
                if (fallbackVoice) {
                    utterance.voice = fallbackVoice;
                }
            }

            const detachListeners = (handler: () => void): void => {
                utterance.removeEventListener("end", handler);
                utterance.removeEventListener("error", handler);
            };

            const handleComplete = (): void => {
                detachListeners(handleComplete);

                // If we've already started another utterance, ignore completion
                // of this stale one.
                if (utteranceRef.current !== utterance) {
                    return;
                }

                utteranceRef.current = undefined;
                utteranceCleanupRef.current = undefined;
                setPlayingMessageId(undefined);
            };

            utterance.addEventListener("end", handleComplete);
            utterance.addEventListener("error", handleComplete);

            utteranceRef.current = utterance;
            utteranceCleanupRef.current = (): void => {
                detachListeners(handleComplete);
            };
            setPlayingMessageId(messageId);
            window.speechSynthesis.speak(utterance);
        },
        [enabled, playingMessageId, preferredVoice, stop],
    );

    return {
        speak,
        stop,
        playingMessageId,
    };
};
