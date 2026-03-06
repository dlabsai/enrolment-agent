import { Button } from "@va/shared/components/ui/button";
import { cn } from "@va/shared/lib/utils";
import { Mic, Square } from "lucide-react";
import type { JSX } from "react";

interface STTButtonProps {
    isRecording: boolean;
    onClick: () => void;
    disabled: boolean;
    suppressFocusRing?: boolean;
}

export const STTButton = ({
    isRecording,
    onClick,
    disabled,
    suppressFocusRing = false,
}: STTButtonProps): JSX.Element => {
    const Icon = isRecording ? Square : Mic;

    return (
        <Button
            aria-label={isRecording ? "Stop recording" : "Start voice input"}
            className={cn(
                "rounded-full transition",
                isRecording && "bg-primary/10 text-primary hover:bg-primary/20",
                suppressFocusRing &&
                    "focus-visible:border-transparent focus-visible:ring-0 focus-visible:ring-offset-0",
            )}
            disabled={disabled}
            onClick={onClick}
            size="icon"
            type="button"
            variant="ghost"
        >
            <Icon
                aria-hidden="true"
                className="size-4"
            />
        </Button>
    );
};
