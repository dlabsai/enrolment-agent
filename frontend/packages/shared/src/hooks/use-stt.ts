import { logger } from "@va/shared/lib/logger";
import { useCallback, useEffect, useRef, useState } from "react";

interface UseSTTOptions {
    enabled: boolean;
    lang: string;
    continuous: boolean;

    /**
     * Called whenever the SpeechRecognition API produces finalized transcript chunks.
     * This is invoked from the underlying event callback (not a React effect).
     */
    onFinalTranscript?: (chunk: string) => void;
}

export const useSTT = ({
    enabled,
    lang,
    continuous,
    onFinalTranscript,
}: UseSTTOptions): {
    start: () => void;
    stop: () => void;
    isRecording: boolean;
    transcript: string;
    clearTranscript: () => void;
    supported: boolean;
} => {
    const [isRecording, setIsRecording] = useState(false);
    const [transcript, setTranscript] = useState("");

    const SpeechRecognition =
        (window.SpeechRecognition as
            | typeof window.SpeechRecognition
            | undefined) ??
        (window.webkitSpeechRecognition as
            | typeof window.webkitSpeechRecognition
            | undefined);
    const supported = SpeechRecognition !== undefined;

    const recognitionRef = useRef<SpeechRecognition | undefined>(undefined);
    const onFinalTranscriptRef = useRef<
        UseSTTOptions["onFinalTranscript"] | undefined
    >(undefined);

    useEffect(() => {
        onFinalTranscriptRef.current = onFinalTranscript;
    }, [onFinalTranscript]);

    useEffect(() => {
        if (!enabled || !supported) {
            return (): void => {
                recognitionRef.current?.stop();
                recognitionRef.current = undefined;
            };
        }

        const recognition = new SpeechRecognition();

        recognition.continuous = continuous;
        recognition.interimResults = true;
        recognition.lang = lang;

        // Immediate UI toggle: flip to "recording" when recognition starts.
        const onStart = (): void => {
            setIsRecording(true);
        };

        const onEnd = (): void => {
            setIsRecording(false);
        };

        const onError = (event: SpeechRecognitionErrorEvent): void => {
            logger.error("Speech recognition error:", event.error);
            setIsRecording(false);
        };

        const onResult = (event: SpeechRecognitionEvent): void => {
            let finalTranscript = "";

            // If continuous: event.results can include previous results.
            // Start at resultIndex for proper concatenation.
            for (
                let index = event.resultIndex;
                index < event.results.length;
                index += 1
            ) {
                const result = event.results.item(index);
                if (result.isFinal) {
                    finalTranscript += result[0].transcript;
                }
            }

            const finalized = finalTranscript.trim();
            if (finalized === "") {
                return;
            }

            const callback = onFinalTranscriptRef.current;
            if (callback) {
                callback(finalized);
            } else {
                setTranscript(finalized);
            }
        };

        recognition.addEventListener("start", onStart);
        recognition.addEventListener("end", onEnd);
        recognition.addEventListener("error", onError);
        recognition.addEventListener("result", onResult);

        recognitionRef.current = recognition;

        return (): void => {
            recognition.removeEventListener("start", onStart);
            recognition.removeEventListener("end", onEnd);
            recognition.removeEventListener("error", onError);
            recognition.removeEventListener("result", onResult);
            recognition.stop();
            if (recognitionRef.current === recognition) {
                recognitionRef.current = undefined;
            }
        };
    }, [enabled, supported, lang, continuous, SpeechRecognition]);

    const start = useCallback(() => {
        if (!enabled || !supported || !recognitionRef.current) {
            return;
        }
        try {
            recognitionRef.current.start();
        } catch (error) {
            logger.error("Error starting speech recognition:", error);
        }
    }, [enabled, supported]);

    const stop = useCallback(() => {
        if (!recognitionRef.current) {
            return;
        }
        // Optimistic UI update: the browser mic indicator may stop slightly later.
        setIsRecording(false);
        recognitionRef.current.stop();
    }, []);

    const clearTranscript = useCallback(() => {
        setTranscript("");
    }, []);

    return {
        start,
        stop,
        isRecording,
        transcript,
        clearTranscript,
        supported: enabled && supported,
    };
};
