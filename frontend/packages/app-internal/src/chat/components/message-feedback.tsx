import { Button } from "@va/shared/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@va/shared/components/ui/dialog";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@va/shared/components/ui/popover";
import { Textarea } from "@va/shared/components/ui/textarea";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@va/shared/components/ui/tooltip";
import { MessageSquareText, ThumbsDown, ThumbsUp, Users } from "lucide-react";
import { type JSX, useEffect, useMemo, useState } from "react";

import { useChatActions, useChatStore } from "../contexts/chat-store-context";
import type { MessageFeedback as MessageFeedbackEntry, Rating } from "../types";

const emptyFeedbackList: MessageFeedbackEntry[] = [];

interface OtherFeedbacksPopoverProps {
    feedbacks: MessageFeedbackEntry[];
}

const OtherFeedbacksPopover = ({
    feedbacks,
}: OtherFeedbacksPopoverProps): JSX.Element => {
    const thumbsUpCount = feedbacks.filter(
        (item) => item.rating === "thumbsUp",
    ).length;
    const thumbsDownCount = feedbacks.filter(
        (item) => item.rating === "thumbsDown",
    ).length;

    return (
        <Popover>
            <Tooltip>
                <TooltipTrigger asChild>
                    <PopoverTrigger asChild>
                        <Button
                            aria-label={`${feedbacks.length} other feedback${feedbacks.length === 1 ? "" : "s"}`}
                            className="text-muted-foreground rounded-full transition"
                            size="icon-sm"
                            type="button"
                            variant="ghost"
                        >
                            <Users
                                aria-hidden="true"
                                className="size-4"
                            />
                            <span className="sr-only">
                                {feedbacks.length} other feedback
                                {feedbacks.length === 1 ? "" : "s"}
                            </span>
                        </Button>
                    </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent>
                    {feedbacks.length} other feedback
                    {feedbacks.length === 1 ? "" : "s"}
                    {thumbsUpCount > 0 && ` (${thumbsUpCount} positive)`}
                    {thumbsDownCount > 0 && ` (${thumbsDownCount} negative)`}
                </TooltipContent>
            </Tooltip>
            <PopoverContent
                align="start"
                className="w-80"
            >
                <div className="space-y-3">
                    <h4 className="font-medium">Other Feedback</h4>
                    <ul className="space-y-2">
                        {feedbacks.map((item) => (
                            <li
                                className="flex items-start gap-2 text-sm"
                                key={item.id}
                            >
                                {item.rating === "thumbsUp" ? (
                                    <ThumbsUp className="text-primary mt-0.5 size-4 shrink-0" />
                                ) : (
                                    <ThumbsDown className="text-destructive mt-0.5 size-4 shrink-0" />
                                )}
                                <div className="min-w-0 flex-1">
                                    <span className="font-medium">
                                        {item.user_name}
                                    </span>
                                    {item.text !== undefined &&
                                        item.text.trim() !== "" && (
                                            <p className="text-muted-foreground mt-0.5 break-words">
                                                {item.text}
                                            </p>
                                        )}
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>
            </PopoverContent>
        </Popover>
    );
};

interface MessageFeedbackProps {
    messageId: string;
    isEligible?: boolean;
    onFeedbackChange?: (change: { previous?: Rating; next?: Rating }) => void;
}

export const MessageFeedback = ({
    messageId,
    isEligible = true,
    onFeedbackChange,
}: MessageFeedbackProps): JSX.Element | undefined => {
    const feedbackList = useChatStore(
        (state) => state.messageFeedback.get(messageId) ?? emptyFeedbackList,
    );
    const isLoaded = useChatStore((state) =>
        state.messageFeedback.has(messageId),
    );
    const isLoading = useChatStore((state) =>
        state.messageFeedbackLoading.has(messageId),
    );

    const {
        loadMessageFeedback,
        submitMessageFeedback,
        removeMessageFeedback,
    } = useChatActions();

    const [dialogOpen, setDialogOpen] = useState(false);
    const [feedbackText, setFeedbackText] = useState("");

    useEffect(() => {
        if (!isEligible) {
            return;
        }
        if (!isLoaded) {
            void loadMessageFeedback(messageId);
        }
    }, [isEligible, isLoaded, loadMessageFeedback, messageId]);

    const currentUserFeedback = useMemo(
        () => feedbackList.find((item) => item.is_current_user),
        [feedbackList],
    );

    const otherFeedbacks = useMemo(
        () => feedbackList.filter((item) => !item.is_current_user),
        [feedbackList],
    );

    const currentRating = currentUserFeedback?.rating;

    const hasFeedbackText =
        currentUserFeedback?.text !== undefined &&
        currentUserFeedback.text.trim() !== "";

    const positiveTooltip = useMemo(() => {
        if (currentRating === "thumbsUp") {
            return "Edit or remove feedback";
        }
        return "Good response";
    }, [currentRating]);

    const negativeTooltip = useMemo(() => {
        if (currentRating === "thumbsDown") {
            return "Edit or remove feedback";
        }
        return "Poor response";
    }, [currentRating]);

    const handleFeedbackClick = async (rating: Rating): Promise<void> => {
        if (!isEligible) {
            return;
        }

        if (currentUserFeedback?.rating === rating) {
            setFeedbackText(currentUserFeedback.text ?? "");
            setDialogOpen(true);
            return;
        }

        await submitMessageFeedback(
            messageId,
            rating,
            currentUserFeedback?.text ?? undefined,
        );
        onFeedbackChange?.({
            previous: currentUserFeedback?.rating,
            next: rating,
        });
    };

    const handleSave = (): void => {
        if (!currentUserFeedback) {
            return;
        }
        void submitMessageFeedback(
            messageId,
            currentUserFeedback.rating,
            feedbackText,
        );
        setDialogOpen(false);
    };

    const handleRemove = async (): Promise<void> => {
        if (!currentUserFeedback) {
            return;
        }
        await removeMessageFeedback(messageId);
        onFeedbackChange?.({
            previous: currentUserFeedback.rating,
            next: undefined,
        });
        setDialogOpen(false);
    };

    if (!isEligible) {
        return undefined;
    }

    return (
        <>
            <div className="flex items-center gap-1">
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            aria-label="Thumbs up"
                            className={
                                currentRating === "thumbsUp"
                                    ? "bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary rounded-full transition"
                                    : "text-muted-foreground rounded-full transition"
                            }
                            disabled={isLoading}
                            onClick={() => {
                                void handleFeedbackClick("thumbsUp");
                            }}
                            size="icon-sm"
                            type="button"
                            variant="ghost"
                        >
                            <ThumbsUp
                                aria-hidden="true"
                                className="size-4"
                            />
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>{positiveTooltip}</TooltipContent>
                </Tooltip>

                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            aria-label="Thumbs down"
                            className={
                                currentRating === "thumbsDown"
                                    ? "bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary rounded-full transition"
                                    : "text-muted-foreground rounded-full transition"
                            }
                            disabled={isLoading}
                            onClick={() => {
                                void handleFeedbackClick("thumbsDown");
                            }}
                            size="icon-sm"
                            type="button"
                            variant="ghost"
                        >
                            <ThumbsDown
                                aria-hidden="true"
                                className="size-4"
                            />
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>{negativeTooltip}</TooltipContent>
                </Tooltip>

                {currentUserFeedback && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                aria-label="Feedback comment"
                                className={
                                    hasFeedbackText
                                        ? "bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary rounded-full transition"
                                        : "text-muted-foreground rounded-full transition"
                                }
                                disabled={isLoading}
                                onClick={() => {
                                    setFeedbackText(
                                        currentUserFeedback.text ?? "",
                                    );
                                    setDialogOpen(true);
                                }}
                                size="icon-sm"
                                type="button"
                                variant="ghost"
                            >
                                <MessageSquareText
                                    aria-hidden="true"
                                    className="size-4"
                                />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                            {hasFeedbackText
                                ? currentUserFeedback.text
                                : "Add feedback comment"}
                        </TooltipContent>
                    </Tooltip>
                )}

                {otherFeedbacks.length > 0 && (
                    <OtherFeedbacksPopover feedbacks={otherFeedbacks} />
                )}
            </div>

            <Dialog
                onOpenChange={(open) => {
                    setDialogOpen(open);
                }}
                open={dialogOpen}
            >
                <DialogContent
                    onInteractOutside={(event) => {
                        event.preventDefault();
                    }}
                    onPointerDownOutside={(event) => {
                        event.preventDefault();
                    }}
                >
                    <DialogHeader>
                        <DialogTitle>Feedback comment</DialogTitle>
                    </DialogHeader>

                    <Textarea
                        disabled={!currentUserFeedback}
                        onChange={(event) => {
                            setFeedbackText(event.target.value);
                        }}
                        placeholder="Additional feedback (optional)"
                        rows={4}
                        value={feedbackText}
                    />

                    <DialogFooter>
                        <Button
                            disabled={!currentUserFeedback || isLoading}
                            onClick={() => {
                                void handleRemove();
                            }}
                            type="button"
                            variant="destructive"
                        >
                            Remove feedback
                        </Button>
                        <Button
                            onClick={() => {
                                setDialogOpen(false);
                            }}
                            type="button"
                            variant="outline"
                        >
                            Cancel
                        </Button>
                        <Button
                            disabled={!currentUserFeedback || isLoading}
                            onClick={handleSave}
                            type="button"
                        >
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};
