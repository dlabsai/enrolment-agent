import { Alert, AlertDescription } from "@va/shared/components/ui/alert";
import { Button } from "@va/shared/components/ui/button";
import { Spinner } from "@va/shared/components/ui/spinner";
import { cn } from "@va/shared/lib/utils";
import { RefreshCw } from "lucide-react";
import type { JSX } from "react";

interface PageLoadingProps {
    message?: string;
    className?: string;
}

export const PageLoading = ({
    message = "Loading...",
    className,
}: PageLoadingProps): JSX.Element => (
    <div
        className={cn(
            "flex h-full flex-1 items-center justify-center",
            className,
        )}
    >
        <div className="text-muted-foreground flex items-center gap-2">
            <Spinner className="size-5" />
            <span>{message}</span>
        </div>
    </div>
);

interface PageErrorProps {
    message: string;
    onRetry?: () => void;
    className?: string;
}

export const PageError = ({
    message,
    onRetry,
    className,
}: PageErrorProps): JSX.Element => (
    <div
        className={cn(
            "flex h-full flex-1 flex-col items-center justify-center gap-4",
            className,
        )}
    >
        <div className="text-destructive">{message}</div>
        {onRetry !== undefined && (
            <Button
                onClick={onRetry}
                variant="outline"
            >
                <RefreshCw className="mr-2 size-4" />
                Retry
            </Button>
        )}
    </div>
);

interface InlineErrorProps {
    message: string;
    onRetry?: () => void;
    className?: string;
}

export const InlineError = ({
    message,
    onRetry,
    className,
}: InlineErrorProps): JSX.Element => (
    <Alert
        className={cn("mb-4", className)}
        variant="destructive"
    >
        <AlertDescription>
            <div className="flex items-center justify-between gap-2">
                <span>{message}</span>
                {onRetry !== undefined && (
                    <Button
                        onClick={onRetry}
                        size="sm"
                        variant="outline"
                    >
                        Retry
                    </Button>
                )}
            </div>
        </AlertDescription>
    </Alert>
);
