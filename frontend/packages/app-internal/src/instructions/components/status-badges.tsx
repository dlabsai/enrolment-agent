import { Info } from "lucide-react";
import type { JSX } from "react";

import { useInstructionsStore } from "../contexts/instructions-store-context";
import { selectIsLiveDefault } from "../lib/store";

const LiveVersionBadge = (): JSX.Element | undefined => {
    const deployedVersion = useInstructionsStore(
        (state) => state.deployedVersion,
    );

    if (deployedVersion?.id === undefined) {
        return undefined;
    }

    return (
        <span className="bg-status-live text-status-live-foreground flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium">
            <span className="bg-status-live-foreground size-2 rounded-full" />
            Live: v{deployedVersion.version_number} – {deployedVersion.name}
        </span>
    );
};

const DefaultBadge = (): JSX.Element | undefined => {
    const isLiveDefault = useInstructionsStore(selectIsLiveDefault);

    if (!isLiveDefault) {
        return undefined;
    }

    return (
        <span className="text-muted-foreground bg-muted flex items-center gap-2 rounded-full px-3 py-1 text-sm">
            <Info className="size-3" />
            Using default instructions
        </span>
    );
};

export const StatusBadges = (): JSX.Element => (
    <div className="flex items-center gap-2">
        <LiveVersionBadge />
        <DefaultBadge />
    </div>
);
