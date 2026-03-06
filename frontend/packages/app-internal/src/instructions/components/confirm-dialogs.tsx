import { ConfirmDialog } from "@va/shared/components/dialog";
import { type JSX, useEffect, useRef } from "react";

import {
    useInstructionsActions,
    useInstructionsStore,
} from "../contexts/instructions-store-context";
import type { ConfirmDialogAction } from "../types";

const DIALOG_CONFIGS: Record<
    ConfirmDialogAction,
    { title: string; description: string; confirmLabel: string }
> = {
    "delete-version": {
        title: "Delete version",
        description:
            "Are you sure you want to delete this version? This action cannot be undone.",
        confirmLabel: "Delete",
    },
    "switch-version": {
        title: "Discard drafts",
        description:
            "You have unsaved changes. Switching versions will discard all your drafts. Are you sure?",
        confirmLabel: "Discard",
    },
    "select-default": {
        title: "Discard drafts",
        description:
            "You have unsaved changes. Selecting Default will discard all your drafts. Are you sure?",
        confirmLabel: "Discard",
    },
    "reset-template": {
        title: "Discard draft",
        description: "Are you sure you want to discard your changes?",
        confirmLabel: "Discard",
    },
};

export const ConfirmDialogs = (): JSX.Element | undefined => {
    const confirmDialogAction = useInstructionsStore(
        (state) => state.confirmDialogAction,
    );
    const confirmDialogVersionId = useInstructionsStore(
        (state) => state.confirmDialogVersionId,
    );

    const { closeConfirmDialog, confirmAction } = useInstructionsActions();

    const actionRef = useRef<ConfirmDialogAction | undefined>(undefined);
    const versionIdRef = useRef<string | undefined>(undefined);

    useEffect(() => {
        if (confirmDialogAction !== undefined) {
            actionRef.current = confirmDialogAction;
            versionIdRef.current = confirmDialogVersionId;
        }
    }, [confirmDialogAction, confirmDialogVersionId]);

    if (confirmDialogAction === undefined) {
        return undefined;
    }

    const config = DIALOG_CONFIGS[confirmDialogAction];

    const handleConfirm = async (): Promise<void> => {
        const action = actionRef.current;
        if (action === undefined) {
            return;
        }
        await confirmAction();
    };

    const handleOpenChange = (open: boolean): void => {
        if (!open) {
            closeConfirmDialog();
        }
    };

    return (
        <ConfirmDialog
            cancelLabel="Cancel"
            confirmLabel={config.confirmLabel}
            description={config.description}
            onConfirm={handleConfirm}
            onOpenChange={handleOpenChange}
            open
            title={config.title}
        />
    );
};
