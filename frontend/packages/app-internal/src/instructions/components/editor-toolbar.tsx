import { Button } from "@va/shared/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@va/shared/components/ui/select";
import {
    Sheet,
    SheetContent,
    SheetTrigger,
} from "@va/shared/components/ui/sheet";
import { useSidebar } from "@va/shared/components/ui/sidebar";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@va/shared/components/ui/tooltip";
import {
    GitCompareArrows,
    Menu,
    MessageSquareText,
    PanelLeft,
    Rocket,
    Trash2,
    WrapText,
} from "lucide-react";
import { type JSX, useMemo } from "react";

import {
    useInstructionsActions,
    useInstructionsStore,
} from "../contexts/instructions-store-context";
import { isAssistantSectionId } from "../lib/sections";
import { HelpButton } from "./help-guide";
import { InstructionsSidebar } from "./instructions-sidebar";
import { SaveDialog } from "./save-panel";
import { StatusBadges } from "./status-badges";

const DEFAULT_VERSION_OPTION = "default";

export const EditorToolbar = (): JSX.Element | undefined => {
    const selectedTemplate = useInstructionsStore(
        (state) => state.selectedTemplate,
    );
    const selectedVersionDetail = useInstructionsStore(
        (state) => state.selectedVersionDetail,
    );
    const deployedVersion = useInstructionsStore(
        (state) => state.deployedVersion,
    );
    const showDiff = useInstructionsStore((state) => state.showDiff);
    const wrapLines = useInstructionsStore((state) => state.wrapLines);
    const activeSectionId = useInstructionsStore(
        (state) => state.activeSectionId,
    );
    const versionsBySection = useInstructionsStore(
        (state) => state.versionsBySection,
    );
    const versions =
        activeSectionId === undefined
            ? []
            : (versionsBySection[activeSectionId] ?? []);
    const selectedVersionId = useInstructionsStore(
        (state) => state.selectedVersionId,
    );
    const isDefaultSelected = useInstructionsStore(
        (state) => state.isDefaultSelected,
    );
    const diskTemplates = useInstructionsStore((state) => state.diskTemplates);
    const drafts = useInstructionsStore((state) => state.drafts);
    const isDeploying = useInstructionsStore((state) => state.isDeploying);
    const isDeleting = useInstructionsStore((state) => state.isDeleting);
    const isChatPanelOpen = useInstructionsStore(
        (state) => state.isChatPanelOpen,
    );

    const { toggleSidebar } = useSidebar();

    const isModified =
        selectedTemplate === undefined ? false : selectedTemplate in drafts;

    const {
        toggleDiff,
        toggleWrapLines,
        requestResetTemplate,
        requestSelectDefault,
        requestSelectVersion,
        deployVersion,
        undeployVersion,
        requestDeleteVersion,
        toggleChatPanel,
    } = useInstructionsActions();

    const selectedVersion = versions.find(
        (version) => version.id === selectedVersionId,
    );
    const selectedVersionIdValue = selectedVersion?.id;

    const versionValue =
        isDefaultSelected || selectedVersionId === undefined
            ? DEFAULT_VERSION_OPTION
            : selectedVersionId;

    const canDeploy =
        selectedVersion !== undefined && !selectedVersion.is_deployed;
    const canUndeploy = isDefaultSelected && deployedVersion?.id !== undefined;
    const canDelete =
        selectedVersion !== undefined && !selectedVersion.is_deployed;
    const loading = isDeploying || isDeleting;

    const modifiedPromptsCount = useMemo(() => {
        if (!selectedVersionDetail) {
            return 0;
        }
        return selectedVersionDetail.prompts.filter((prompt) => {
            const diskTemplate = diskTemplates.find(
                (template) => template.filename === prompt.filename,
            );
            const currentContent = drafts[prompt.filename] ?? prompt.content;
            return diskTemplate?.content !== currentContent;
        }).length;
    }, [diskTemplates, drafts, selectedVersionDetail]);

    const showVersionControls = activeSectionId !== undefined;
    const showTestChatToggle = isAssistantSectionId(activeSectionId);

    return (
        <div className="border-border border-b px-2 py-2">
            <div className="flex flex-wrap items-center gap-2">
                <Button
                    className="md:hidden"
                    onClick={toggleSidebar}
                    size="icon-sm"
                    type="button"
                    variant="outline"
                >
                    <PanelLeft className="size-4" />
                    <span className="sr-only">Open sidebar</span>
                </Button>
                <Sheet>
                    <SheetTrigger asChild>
                        <Button
                            className="md:hidden"
                            size="icon-sm"
                            type="button"
                            variant="outline"
                        >
                            <Menu className="size-4" />
                            <span className="sr-only">Open navigation</span>
                        </Button>
                    </SheetTrigger>
                    <SheetContent
                        className="w-80! max-w-none! overflow-x-hidden p-0"
                        side="left"
                    >
                        <InstructionsSidebar />
                    </SheetContent>
                </Sheet>
                {showVersionControls && (
                    <Select
                        onValueChange={(value) => {
                            if (value === DEFAULT_VERSION_OPTION) {
                                requestSelectDefault();
                            } else {
                                requestSelectVersion(value);
                            }
                        }}
                        value={versionValue}
                    >
                        <SelectTrigger className="w-48">
                            <SelectValue placeholder="Select version" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value={DEFAULT_VERSION_OPTION}>
                                Default
                            </SelectItem>
                            {versions.map((version) => (
                                <SelectItem
                                    key={version.id}
                                    value={version.id}
                                >
                                    v{version.version_number} – {version.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                )}
                {showVersionControls &&
                    canDeploy &&
                    selectedVersionIdValue !== undefined && (
                        <Button
                            disabled={loading}
                            onClick={() => {
                                void deployVersion(selectedVersionIdValue);
                            }}
                            size="sm"
                            variant="outline"
                        >
                            <Rocket className="mr-2 size-4" />
                            Deploy
                        </Button>
                    )}
                {showVersionControls && canUndeploy && (
                    <Button
                        disabled={loading}
                        onClick={() => {
                            void undeployVersion();
                        }}
                        size="sm"
                        variant="outline"
                    >
                        <Rocket className="mr-2 size-4" />
                        Deploy
                    </Button>
                )}
                {showVersionControls &&
                    canDelete &&
                    selectedVersionIdValue !== undefined && (
                        <Button
                            disabled={loading}
                            onClick={() => {
                                requestDeleteVersion(selectedVersionIdValue);
                            }}
                            size="sm"
                            variant="outline"
                        >
                            <Trash2 className="mr-2 size-4" />
                            Delete
                        </Button>
                    )}
                {selectedTemplate !== undefined && (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    disabled={!isModified}
                                    onClick={toggleDiff}
                                    size="icon-sm"
                                    variant={showDiff ? "secondary" : "outline"}
                                >
                                    <GitCompareArrows className="size-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                {showDiff ? "Hide" : "Show"} diff
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                )}
                {selectedTemplate !== undefined && (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    onClick={toggleWrapLines}
                                    size="icon-sm"
                                    variant={
                                        wrapLines ? "secondary" : "outline"
                                    }
                                >
                                    <WrapText className="size-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                {wrapLines ? "Disable" : "Enable"} line wrapping
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                )}
                {selectedTemplate !== undefined && isModified && (
                    <Button
                        onClick={requestResetTemplate}
                        size="sm"
                        variant="outline"
                    >
                        Reset
                    </Button>
                )}
                <SaveDialog />
                {showTestChatToggle && (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    onClick={toggleChatPanel}
                                    size="icon-sm"
                                    variant={
                                        isChatPanelOpen
                                            ? "secondary"
                                            : "outline"
                                    }
                                >
                                    <MessageSquareText className="size-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                {isChatPanelOpen ? "Hide" : "Show"} test chat
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                )}
                <div className="flex flex-wrap items-center gap-2 md:ml-auto">
                    {selectedTemplate === undefined &&
                        selectedVersionDetail !== undefined && (
                            <div className="text-muted-foreground text-sm">
                                v{selectedVersionDetail.version_number} –{" "}
                                {selectedVersionDetail.name} •{" "}
                                {modifiedPromptsCount} modified •{" "}
                                {selectedVersionDetail.created_by_name}
                            </div>
                        )}
                    <StatusBadges />
                    <HelpButton />
                </div>
            </div>
        </div>
    );
};
