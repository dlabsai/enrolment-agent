import { Terminal } from "@va/shared/components/ai-elements/terminal";
import { Badge } from "@va/shared/components/ui/badge";
import { Button } from "@va/shared/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@va/shared/components/ui/card";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@va/shared/components/ui/command";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@va/shared/components/ui/dialog";
import { Input } from "@va/shared/components/ui/input";
import { Label } from "@va/shared/components/ui/label";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@va/shared/components/ui/popover";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@va/shared/components/ui/select";
import {
    Check,
    ChevronsUpDown,
    Maximize2,
    SlidersHorizontal,
    X,
} from "lucide-react";
import {
    type JSX,
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import { toast } from "sonner";

import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import { ModelSelectionDialogContent } from "../../components/model-selection-dialog-content";
import { InlineError } from "../../components/page-state";
import {
    fetchEvalTestCases,
    fetchInternalModels,
    runEvalStream,
} from "../lib/api";
import {
    type EvalModelPreset,
    readStoredModelConfig,
    readStoredModelFavorites,
    readStoredModelPresets,
    writeStoredModelConfig,
    writeStoredModelFavorites,
    writeStoredModelPresets,
} from "../lib/model-storage";
import {
    parsePassThreshold,
    parsePositiveInt,
    parseTestCaseInput,
    resolveRunStatusLabel,
    resolveRunStatusVariant,
} from "../lib/run-utils";
import type {
    EvalRunLogEntry,
    EvalRunRequest,
    EvalRunStatusEvent,
    EvalSuite,
} from "../types";

const evalSuiteOptions: { label: string; value: EvalSuite }[] = [
    { label: "Chatbot", value: "chatbot" },
    { label: "Guardrails", value: "guardrails" },
    { label: "Search", value: "search" },
];

const DEFAULT_PRESET_VALUE = "__default_preset__";
const COMMAND_UNSELECTED_VALUE = "__va_model_unselected__";
type EvalModelTarget =
    | "chatbot"
    | "guardrails"
    | "extractor"
    | "judge"
    | "search";

const EVAL_MODEL_TARGET_TABS: { value: EvalModelTarget; label: string }[] = [
    { value: "chatbot", label: "Chatbot" },
    { value: "search", label: "Search" },
    { value: "guardrails", label: "Guardrails" },
    { value: "extractor", label: "Extractor" },
    { value: "judge", label: "Judge" },
];

interface EvalRunLogItem extends EvalRunLogEntry {
    id: string;
}

interface EvalsRunCardProps {
    onReportCreated: (reportId: string) => void;
}

export const EvalsRunCard = ({
    onReportCreated,
}: EvalsRunCardProps): JSX.Element => {
    const api = useAuthenticatedApi();
    const [runSuite, setRunSuite] = useState<EvalSuite>("chatbot");
    const [runRepeat, setRunRepeat] = useState("1");
    const [runConcurrency, setRunConcurrency] = useState("5");
    const [runPassThreshold, setRunPassThreshold] = useState("0.9");
    const [selectedTestCases, setSelectedTestCases] = useState<string[]>([]);
    const [testCasesSearch, setTestCasesSearch] = useState("");
    const [testCasesOpen, setTestCasesOpen] = useState(false);
    const [testCasesLoading, setTestCasesLoading] = useState(false);
    const [testCasesError, setTestCasesError] = useState<string | undefined>();
    const [availableTestCases, setAvailableTestCases] = useState<string[]>([]);
    const [availableModels, setAvailableModels] = useState<string[]>([]);
    const [modelsLoading, setModelsLoading] = useState(true);
    const [modelsError, setModelsError] = useState<string | undefined>();
    const [commandValue, setCommandValue] = useState(COMMAND_UNSELECTED_VALUE);
    const [runChatbotModel, setRunChatbotModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.chatbotModel === "string"
            ? stored.chatbotModel
            : "";
    });
    const [runGuardrailModel, setRunGuardrailModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.guardrailModel === "string"
            ? stored.guardrailModel
            : "";
    });
    const [runExtractorModel, setRunExtractorModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.extractorModel === "string"
            ? stored.extractorModel
            : "";
    });
    const [runEvaluationModel, setRunEvaluationModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.evaluationModel === "string"
            ? stored.evaluationModel
            : "";
    });
    const [runSearchModel, setRunSearchModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.searchModel === "string"
            ? stored.searchModel
            : "";
    });
    const [favoriteModels, setFavoriteModels] = useState(() =>
        readStoredModelFavorites(),
    );
    const [modelPresets, setModelPresets] = useState(() =>
        readStoredModelPresets(),
    );
    const [presetName, setPresetName] = useState("");
    const [deletePresetOpen, setDeletePresetOpen] = useState(false);
    const [deletePresetName, setDeletePresetName] = useState<
        string | undefined
    >();
    const [modelTarget, setModelTarget] = useState<EvalModelTarget>("chatbot");
    const [isModelDialogOpen, setIsModelDialogOpen] = useState(false);
    const [runStatus, setRunStatus] = useState<
        EvalRunStatusEvent["status"] | "idle"
    >("idle");
    const [runExitCode, setRunExitCode] = useState<number | undefined>();
    const [runLogs, setRunLogs] = useState<EvalRunLogItem[]>([]);
    const [runError, setRunError] = useState<string | undefined>();
    const [expandedTerminalOpen, setExpandedTerminalOpen] = useState(false);
    const runAbortControllerRef = useRef<AbortController | undefined>(
        undefined,
    );
    const runLogCounterRef = useRef(0);

    const runOutput = useMemo(
        () =>
            runLogs
                .map((entry) => {
                    const line = `[${entry.stream}] ${entry.message}`;
                    if (entry.stream === "stderr") {
                        return `\u001B[31m${line}\u001B[0m`;
                    }
                    return line;
                })
                .join("\n"),
        [runLogs],
    );

    const selectedTestCaseSet = useMemo(
        () => new Set(selectedTestCases),
        [selectedTestCases],
    );

    const filteredTestCases = useMemo(() => {
        const query = testCasesSearch.trim().toLowerCase();
        if (query === "") {
            return availableTestCases;
        }
        return availableTestCases.filter((caseId) =>
            caseId.toLowerCase().includes(query),
        );
    }, [availableTestCases, testCasesSearch]);

    const normalizedTestCaseSearch = testCasesSearch.trim();
    const pendingCustomTestCases = useMemo(
        () => parseTestCaseInput(normalizedTestCaseSearch),
        [normalizedTestCaseSearch],
    );

    const canAddCustomTestCases = pendingCustomTestCases.some(
        (value) =>
            !selectedTestCaseSet.has(value) &&
            !availableTestCases.includes(value),
    );

    const addTestCases = useCallback((caseIds: string[]): void => {
        setSelectedTestCases((prev) => {
            const next = [...prev];
            const seen = new Set(prev);
            for (const caseId of caseIds) {
                const trimmed = caseId.trim();
                if (trimmed !== "" && !seen.has(trimmed)) {
                    seen.add(trimmed);
                    next.push(trimmed);
                }
            }
            return next;
        });
    }, []);

    const removeTestCase = useCallback((caseId: string): void => {
        setSelectedTestCases((prev) =>
            prev.filter((entry) => entry !== caseId),
        );
    }, []);

    const toggleTestCase = useCallback((caseId: string): void => {
        setSelectedTestCases((prev) => {
            if (prev.includes(caseId)) {
                return prev.filter((entry) => entry !== caseId);
            }
            return [...prev, caseId];
        });
    }, []);

    const handleSelectAllTestCases = useCallback((): void => {
        setSelectedTestCases((prev) => {
            const extras = prev.filter(
                (entry) => !availableTestCases.includes(entry),
            );
            return [...extras, ...availableTestCases];
        });
    }, [availableTestCases]);

    const handleClearTestCases = useCallback((): void => {
        setSelectedTestCases([]);
    }, []);

    const testCasesLabel =
        selectedTestCases.length === 0
            ? "All test cases"
            : `${selectedTestCases.length} selected`;

    const testCasesEmptyLabel = testCasesLoading
        ? "Loading test cases..."
        : (testCasesError ?? "No test cases found");

    const appendRunLog = useCallback((entry: EvalRunLogEntry) => {
        setRunLogs((prev) => {
            const next = [
                ...prev,
                {
                    ...entry,
                    id: `log-${runLogCounterRef.current}`,
                },
            ];
            runLogCounterRef.current += 1;
            return next;
        });
    }, []);

    useEffect(() => {
        writeStoredModelConfig({
            chatbotModel: runChatbotModel,
            guardrailModel: runGuardrailModel,
            extractorModel: runExtractorModel,
            evaluationModel: runEvaluationModel,
            searchModel: runSearchModel,
        });
    }, [
        runChatbotModel,
        runEvaluationModel,
        runExtractorModel,
        runGuardrailModel,
        runSearchModel,
    ]);

    useEffect(() => {
        writeStoredModelFavorites(favoriteModels);
    }, [favoriteModels]);

    useEffect(() => {
        writeStoredModelPresets(modelPresets);
    }, [modelPresets]);

    useEffect((): (() => void) | undefined => {
        let mounted = true;
        void fetchInternalModels(api)
            .then((models) => {
                if (!mounted) {
                    return;
                }
                const uniqueModels = [
                    ...new Set(
                        models
                            .map((model) => model.trim())
                            .filter((model) => model !== ""),
                    ),
                ];
                setAvailableModels(uniqueModels);
            })
            .catch((error: unknown) => {
                if (!mounted) {
                    return;
                }
                setModelsError(
                    error instanceof Error
                        ? error.message
                        : "Failed to load models",
                );
            })
            .finally(() => {
                if (!mounted) {
                    return;
                }
                setModelsLoading(false);
            });

        return () => {
            mounted = false;
        };
    }, [api]);

    useEffect((): (() => void) | undefined => {
        let mounted = true;
        setTestCasesLoading(true);
        setTestCasesError(undefined);
        setTestCasesSearch("");
        setAvailableTestCases([]);
        setSelectedTestCases([]);

        void fetchEvalTestCases(api, runSuite)
            .then((cases) => {
                if (!mounted) {
                    return;
                }
                const uniqueCases = [
                    ...new Set(
                        cases
                            .map((value) => value.trim())
                            .filter((value) => value !== ""),
                    ),
                ];
                setAvailableTestCases(uniqueCases);
            })
            .catch((error: unknown) => {
                if (!mounted) {
                    return;
                }
                setTestCasesError(
                    error instanceof Error
                        ? error.message
                        : "Failed to load test cases",
                );
            })
            .finally(() => {
                if (!mounted) {
                    return;
                }
                setTestCasesLoading(false);
            });

        return () => {
            mounted = false;
        };
    }, [api, runSuite]);

    const handleRun = useCallback(async (): Promise<void> => {
        if (runAbortControllerRef.current !== undefined) {
            return;
        }
        const repeat = parsePositiveInt(runRepeat, 1);
        const maxConcurrency = parsePositiveInt(runConcurrency, 5);
        const passThreshold = parsePassThreshold(runPassThreshold, 0.9);
        const testCaseValues = selectedTestCases
            .map((value) => value.trim())
            .filter((value) => value !== "");
        const testCases = testCaseValues.join(",");
        const chatbotModel = runChatbotModel.trim();
        const guardrailModel = runGuardrailModel.trim();
        const extractorModel = runExtractorModel.trim();
        const evaluationModel = runEvaluationModel.trim();
        const searchModel = runSearchModel.trim();

        const payload: EvalRunRequest = {
            suite: runSuite,
            repeat,
            maxConcurrency,
            passThreshold,
            testCases: testCases === "" ? undefined : testCases,
            chatbotModel: chatbotModel === "" ? undefined : chatbotModel,
            guardrailModel: guardrailModel === "" ? undefined : guardrailModel,
            extractorModel: extractorModel === "" ? undefined : extractorModel,
            evaluationModel:
                evaluationModel === "" ? undefined : evaluationModel,
            searchModel: searchModel === "" ? undefined : searchModel,
        };

        const controller = new AbortController();
        runAbortControllerRef.current = controller;
        runLogCounterRef.current = 0;
        setRunLogs([]);
        setRunError(undefined);
        setRunExitCode(undefined);
        setRunStatus("start");

        try {
            await runEvalStream(
                api,
                payload,
                {
                    onLog: (entry) => {
                        appendRunLog(entry);
                    },
                    onStatus: (status) => {
                        setRunStatus(status.status);
                        setRunExitCode(status.exitCode);
                    },
                    onReport: (report) => {
                        onReportCreated(report.reportId);
                    },
                    onError: (message) => {
                        setRunError(message);
                    },
                },
                controller.signal,
            );
        } catch (error_) {
            if (
                error_ instanceof DOMException &&
                error_.name === "AbortError"
            ) {
                setRunStatus("cancelled");
            } else {
                setRunError(
                    error_ instanceof Error
                        ? error_.message
                        : "Failed to run evals",
                );
                setRunStatus("error");
            }
        } finally {
            if (runAbortControllerRef.current === controller) {
                runAbortControllerRef.current = undefined;
            }
        }
    }, [
        api,
        appendRunLog,
        onReportCreated,
        runChatbotModel,
        runConcurrency,
        runEvaluationModel,
        runExtractorModel,
        runGuardrailModel,
        runSearchModel,
        runPassThreshold,
        runRepeat,
        runSuite,
        selectedTestCases,
    ]);

    const handleStop = useCallback((): void => {
        if (runAbortControllerRef.current !== undefined) {
            runAbortControllerRef.current.abort();
        }
    }, []);

    const favoriteModelsAvailable = useMemo(
        () => favoriteModels.filter((model) => availableModels.includes(model)),
        [favoriteModels, availableModels],
    );

    const favoriteModelSet = useMemo(
        () => new Set(favoriteModelsAvailable),
        [favoriteModelsAvailable],
    );

    const sortedFavoriteModels = useMemo(
        () =>
            favoriteModelsAvailable.toSorted((left, right) =>
                left.localeCompare(right),
            ),
        [favoriteModelsAvailable],
    );

    const groupedModels = useMemo(() => {
        const groups = new Map<string, string[]>();
        for (const model of availableModels) {
            if (!favoriteModelSet.has(model)) {
                const separatorIndex = model.indexOf(":");
                const provider =
                    separatorIndex > 0
                        ? model.slice(0, separatorIndex)
                        : "default";
                const name =
                    separatorIndex > 0
                        ? model.slice(separatorIndex + 1)
                        : model;
                const entries = groups.get(provider) ?? [];
                entries.push(name);
                groups.set(provider, entries);
            }
        }
        return [...groups.entries()].map(([provider, models]) => ({
            provider,
            models: models.toSorted((left, right) => left.localeCompare(right)),
        }));
    }, [availableModels, favoriteModelSet]);

    const currentTargetValue =
        modelTarget === "guardrails"
            ? runGuardrailModel
            : modelTarget === "extractor"
              ? runExtractorModel
              : modelTarget === "judge"
                ? runEvaluationModel
                : modelTarget === "search"
                  ? runSearchModel
                  : runChatbotModel;

    const setModelForTarget = (value: string): void => {
        const normalizedValue = value === "" ? "" : value;
        if (modelTarget === "guardrails") {
            setRunGuardrailModel(normalizedValue);
            return;
        }
        if (modelTarget === "extractor") {
            setRunExtractorModel(normalizedValue);
            return;
        }
        if (modelTarget === "judge") {
            setRunEvaluationModel(normalizedValue);
            return;
        }
        if (modelTarget === "search") {
            setRunSearchModel(normalizedValue);
            return;
        }
        setRunChatbotModel(normalizedValue);
    };

    const resetCurrentTarget = (): void => {
        setModelForTarget("");
    };

    const toggleFavoriteModel = (model: string): void => {
        setFavoriteModels((current) => {
            if (current.includes(model)) {
                return current.filter((entry) => entry !== model);
            }
            return [...current, model];
        });
    };

    const modelOverrideSummary = useMemo((): string[] => {
        const summary: string[] = [];
        if (runChatbotModel !== "") {
            summary.push(`Chatbot: ${runChatbotModel}`);
        }
        if (runGuardrailModel !== "") {
            summary.push(`Guardrails: ${runGuardrailModel}`);
        }
        if (runExtractorModel !== "") {
            summary.push(`Extractor: ${runExtractorModel}`);
        }
        if (runEvaluationModel !== "") {
            summary.push(`Judge: ${runEvaluationModel}`);
        }
        if (runSearchModel !== "") {
            summary.push(`Search: ${runSearchModel}`);
        }
        return summary;
    }, [
        runChatbotModel,
        runEvaluationModel,
        runExtractorModel,
        runGuardrailModel,
        runSearchModel,
    ]);

    const hasModelOverrides = modelOverrideSummary.length > 0;

    const activePresetName = useMemo(() => {
        for (const preset of modelPresets) {
            if (
                (preset.chatbotModel ?? "") === runChatbotModel &&
                (preset.searchModel ?? "") === runSearchModel &&
                (preset.guardrailModel ?? "") === runGuardrailModel &&
                (preset.extractorModel ?? "") === runExtractorModel &&
                (preset.evaluationModel ?? "") === runEvaluationModel
            ) {
                return preset.name;
            }
        }
        return "";
    }, [
        modelPresets,
        runChatbotModel,
        runEvaluationModel,
        runExtractorModel,
        runGuardrailModel,
        runSearchModel,
    ]);

    const sortedPresets = useMemo(
        () =>
            [...modelPresets].toSorted((left, right) =>
                left.name.localeCompare(right.name),
            ),
        [modelPresets],
    );

    const presetSelectValue =
        activePresetName === "" ? DEFAULT_PRESET_VALUE : activePresetName;

    const buildPresetFromCurrent = (name: string): EvalModelPreset => {
        const preset: EvalModelPreset = { name };
        if (runChatbotModel !== "") {
            preset.chatbotModel = runChatbotModel;
        }
        if (runSearchModel !== "") {
            preset.searchModel = runSearchModel;
        }
        if (runGuardrailModel !== "") {
            preset.guardrailModel = runGuardrailModel;
        }
        if (runExtractorModel !== "") {
            preset.extractorModel = runExtractorModel;
        }
        if (runEvaluationModel !== "") {
            preset.evaluationModel = runEvaluationModel;
        }
        return preset;
    };

    const applyPreset = (preset: EvalModelPreset): void => {
        setRunChatbotModel(preset.chatbotModel ?? "");
        setRunSearchModel(preset.searchModel ?? "");
        setRunGuardrailModel(preset.guardrailModel ?? "");
        setRunExtractorModel(preset.extractorModel ?? "");
        setRunEvaluationModel(preset.evaluationModel ?? "");
    };

    const handlePresetSelect = (value: string): void => {
        if (value === DEFAULT_PRESET_VALUE) {
            return;
        }
        const preset = modelPresets.find((entry) => entry.name === value);
        if (!preset) {
            return;
        }
        applyPreset(preset);
    };

    const handleSavePreset = (): void => {
        const trimmed = presetName.trim();
        if (trimmed === "") {
            toast.error("Preset name is required");
            return;
        }
        const nextPreset = buildPresetFromCurrent(trimmed);
        setModelPresets((current) => {
            const withoutExisting = current.filter(
                (preset) => preset.name !== trimmed,
            );
            return [...withoutExisting, nextPreset];
        });
        setPresetName("");
        toast.success(`Saved preset "${trimmed}"`);
    };

    const openDeletePresetDialog = (name: string): void => {
        const existing = modelPresets.find((preset) => preset.name === name);
        if (!existing) {
            return;
        }
        setDeletePresetName(name);
        setDeletePresetOpen(true);
    };

    const handleDeletePreset = (): void => {
        const name = deletePresetName;
        if (name === undefined || name === "") {
            return;
        }
        setModelPresets((current) =>
            current.filter((preset) => preset.name !== name),
        );
        setDeletePresetOpen(false);
        setDeletePresetName(undefined);
        toast.success(`Deleted preset "${name}"`);
    };

    const runStatusLabel = resolveRunStatusLabel(runStatus, runExitCode);
    const runStatusVariant = resolveRunStatusVariant(runStatus);
    const runIsRunning = runStatus === "start";
    const runOutputDisplay = runOutput === "" ? "No output yet." : runOutput;

    return (
        <Card>
            <CardHeader className="gap-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                        <CardTitle>Run evals</CardTitle>
                        <CardDescription>
                            Trigger the CLI eval suites and stream output as
                            they run.
                        </CardDescription>
                    </div>
                    <Badge variant={runStatusVariant}>{runStatusLabel}</Badge>
                </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
                <div className="grid gap-3 @lg/main:grid-cols-4">
                    <div className="flex flex-col gap-1">
                        <Label className="text-muted-foreground text-xs">
                            Suite
                        </Label>
                        <Select
                            onValueChange={(value) => {
                                if (
                                    value === "chatbot" ||
                                    value === "guardrails" ||
                                    value === "search"
                                ) {
                                    setRunSuite(value);
                                }
                            }}
                            value={runSuite}
                        >
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select suite" />
                            </SelectTrigger>
                            <SelectContent>
                                {evalSuiteOptions.map((suite) => (
                                    <SelectItem
                                        key={suite.value}
                                        value={suite.value}
                                    >
                                        {suite.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <Label className="text-muted-foreground text-xs">
                            Repeats
                        </Label>
                        <Input
                            min={1}
                            onChange={(event) => {
                                setRunRepeat(event.target.value);
                            }}
                            type="number"
                            value={runRepeat}
                        />
                    </div>
                    <div className="flex flex-col gap-1">
                        <Label className="text-muted-foreground text-xs">
                            Concurrency
                        </Label>
                        <Input
                            min={1}
                            onChange={(event) => {
                                setRunConcurrency(event.target.value);
                            }}
                            type="number"
                            value={runConcurrency}
                        />
                    </div>
                    <div className="flex flex-col gap-1">
                        <Label className="text-muted-foreground text-xs">
                            Pass threshold
                        </Label>
                        <Input
                            max={1}
                            min={0.1}
                            onChange={(event) => {
                                setRunPassThreshold(event.target.value);
                            }}
                            step={0.01}
                            type="number"
                            value={runPassThreshold}
                        />
                    </div>
                    <div className="flex flex-col gap-1 @lg/main:col-span-4">
                        <Label className="text-muted-foreground text-xs">
                            Test case IDs
                        </Label>
                        <Popover
                            onOpenChange={(nextOpen) => {
                                setTestCasesOpen(nextOpen);
                                if (!nextOpen) {
                                    setTestCasesSearch("");
                                }
                            }}
                            open={testCasesOpen}
                        >
                            <PopoverTrigger asChild>
                                <Button
                                    aria-expanded={testCasesOpen}
                                    className="h-9 justify-between"
                                    role="combobox"
                                    type="button"
                                    variant="outline"
                                >
                                    <span className="truncate">
                                        {testCasesLabel}
                                    </span>
                                    <ChevronsUpDown className="text-muted-foreground size-4" />
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent
                                align="start"
                                className="w-[340px] p-0"
                            >
                                <Command shouldFilter={false}>
                                    <CommandInput
                                        onValueChange={setTestCasesSearch}
                                        placeholder="Search or add test cases..."
                                        value={testCasesSearch}
                                    />
                                    <div className="text-muted-foreground flex items-center justify-between gap-2 border-b px-3 py-2 text-xs">
                                        <span>
                                            {availableTestCases.length}{" "}
                                            available
                                        </span>
                                        <div className="flex items-center gap-2">
                                            <Button
                                                disabled={
                                                    availableTestCases.length ===
                                                    0
                                                }
                                                onClick={
                                                    handleSelectAllTestCases
                                                }
                                                size="sm"
                                                type="button"
                                                variant="ghost"
                                            >
                                                Select all
                                            </Button>
                                            <Button
                                                disabled={
                                                    selectedTestCases.length ===
                                                    0
                                                }
                                                onClick={handleClearTestCases}
                                                size="sm"
                                                type="button"
                                                variant="ghost"
                                            >
                                                Clear
                                            </Button>
                                        </div>
                                    </div>
                                    <CommandList>
                                        <CommandEmpty>
                                            {testCasesEmptyLabel}
                                        </CommandEmpty>
                                        <CommandGroup>
                                            {filteredTestCases.map((caseId) => {
                                                const isSelected =
                                                    selectedTestCaseSet.has(
                                                        caseId,
                                                    );
                                                return (
                                                    <CommandItem
                                                        key={caseId}
                                                        onSelect={() => {
                                                            toggleTestCase(
                                                                caseId,
                                                            );
                                                        }}
                                                        value={caseId}
                                                    >
                                                        <Check
                                                            className={`size-4 ${isSelected ? "opacity-100" : "opacity-0"}`}
                                                        />
                                                        <span className="truncate">
                                                            {caseId}
                                                        </span>
                                                    </CommandItem>
                                                );
                                            })}
                                            {canAddCustomTestCases && (
                                                <CommandItem
                                                    onSelect={() => {
                                                        addTestCases(
                                                            pendingCustomTestCases,
                                                        );
                                                        setTestCasesSearch("");
                                                    }}
                                                    value={
                                                        normalizedTestCaseSearch
                                                    }
                                                >
                                                    <Check className="size-4 opacity-0" />
                                                    <span>
                                                        Add{" "}
                                                        {
                                                            normalizedTestCaseSearch
                                                        }
                                                    </span>
                                                </CommandItem>
                                            )}
                                        </CommandGroup>
                                    </CommandList>
                                </Command>
                            </PopoverContent>
                        </Popover>
                        {selectedTestCases.length > 0 && (
                            <div className="flex flex-wrap gap-2 pt-2">
                                {selectedTestCases.map((caseId) => (
                                    <Badge
                                        className="gap-1"
                                        key={caseId}
                                        variant="secondary"
                                    >
                                        <span>{caseId}</span>
                                        <button
                                            aria-label={`Remove ${caseId}`}
                                            className="text-muted-foreground hover:text-foreground"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                removeTestCase(caseId);
                                            }}
                                            type="button"
                                        >
                                            <X className="size-3" />
                                        </button>
                                    </Badge>
                                ))}
                            </div>
                        )}
                    </div>
                    <div className="flex flex-col gap-2 @lg/main:col-span-4">
                        <Label className="text-muted-foreground text-xs">
                            Models (optional)
                        </Label>
                        <div className="flex flex-wrap items-center gap-2">
                            <Dialog
                                onOpenChange={(nextOpen) => {
                                    setIsModelDialogOpen(nextOpen);
                                    if (nextOpen) {
                                        setCommandValue(
                                            COMMAND_UNSELECTED_VALUE,
                                        );
                                    }
                                }}
                                open={isModelDialogOpen}
                            >
                                <DialogTrigger asChild>
                                    <Button
                                        size="sm"
                                        type="button"
                                        variant="outline"
                                    >
                                        <SlidersHorizontal className="mr-2 size-4" />
                                        Model selection
                                    </Button>
                                </DialogTrigger>
                                <ModelSelectionDialogContent
                                    commandValue={commandValue}
                                    currentTargetValue={currentTargetValue}
                                    defaultPresetValue={DEFAULT_PRESET_VALUE}
                                    deletePresetName={deletePresetName}
                                    deletePresetOpen={deletePresetOpen}
                                    favoriteModelSet={favoriteModelSet}
                                    favoriteModels={sortedFavoriteModels}
                                    groupedModels={groupedModels}
                                    isSaveDisabled={presetName.trim() === ""}
                                    modelTarget={modelTarget}
                                    modelsError={modelsError}
                                    modelsLoading={modelsLoading}
                                    onCommandReset={() => {
                                        setCommandValue(
                                            COMMAND_UNSELECTED_VALUE,
                                        );
                                    }}
                                    onCommandValueChange={setCommandValue}
                                    onDeletePresetCancel={() => {
                                        setDeletePresetOpen(false);
                                        setDeletePresetName(undefined);
                                    }}
                                    onDeletePresetConfirm={handleDeletePreset}
                                    onDeletePresetOpenChange={(nextOpen) => {
                                        setDeletePresetOpen(nextOpen);
                                        if (!nextOpen) {
                                            setDeletePresetName(undefined);
                                        }
                                    }}
                                    onModelTargetChange={setModelTarget}
                                    onPresetNameChange={setPresetName}
                                    onPresetSelect={handlePresetSelect}
                                    onRequestDeletePreset={
                                        openDeletePresetDialog
                                    }
                                    onResetCurrentTarget={resetCurrentTarget}
                                    onSavePreset={handleSavePreset}
                                    onSelectModel={setModelForTarget}
                                    onToggleFavorite={toggleFavoriteModel}
                                    presetName={presetName}
                                    presetSelectValue={presetSelectValue}
                                    presets={sortedPresets}
                                    resetButtonAriaLabel="Reset model to default"
                                    tabs={EVAL_MODEL_TARGET_TABS}
                                />
                            </Dialog>
                            {hasModelOverrides && (
                                <Button
                                    onClick={() => {
                                        setRunChatbotModel("");
                                        setRunGuardrailModel("");
                                        setRunExtractorModel("");
                                        setRunEvaluationModel("");
                                        setRunSearchModel("");
                                    }}
                                    size="sm"
                                    type="button"
                                    variant="ghost"
                                >
                                    Reset models
                                </Button>
                            )}
                        </div>
                        {hasModelOverrides ? (
                            <div className="text-muted-foreground text-xs">
                                {modelOverrideSummary.join(" · ")}
                            </div>
                        ) : (
                            <div className="text-muted-foreground text-xs">
                                Using default models.
                            </div>
                        )}
                    </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <Button
                        disabled={runIsRunning}
                        onClick={() => void handleRun()}
                        size="sm"
                    >
                        Run evals
                    </Button>
                    <Button
                        disabled={!runIsRunning}
                        onClick={handleStop}
                        size="sm"
                        variant="outline"
                    >
                        Stop
                    </Button>
                    <Button
                        onClick={() => {
                            runLogCounterRef.current = 0;
                            setRunLogs([]);
                            setRunError(undefined);
                            setRunExitCode(undefined);
                            setRunStatus("idle");
                        }}
                        size="sm"
                        variant="outline"
                    >
                        Clear logs
                    </Button>
                    <Dialog
                        onOpenChange={setExpandedTerminalOpen}
                        open={expandedTerminalOpen}
                    >
                        <DialogTrigger asChild>
                            <Button
                                size="sm"
                                variant="outline"
                            >
                                <Maximize2 className="mr-2 size-4" />
                                Expand terminal
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="flex h-[90vh] w-[94vw] max-w-[94vw] flex-col sm:max-w-[94vw]">
                            <DialogHeader>
                                <DialogTitle>Eval run output</DialogTitle>
                                <DialogDescription>
                                    Live stream output in a larger view.
                                </DialogDescription>
                            </DialogHeader>
                            <Terminal
                                className="min-h-0 flex-1 [&>div:last-child]:h-full [&>div:last-child]:max-h-none"
                                isStreaming={runIsRunning}
                                output={runOutputDisplay}
                            />
                        </DialogContent>
                    </Dialog>
                </div>
                {runError !== undefined && <InlineError message={runError} />}
                {!expandedTerminalOpen && (
                    <Terminal
                        className="[&>div:last-child]:max-h-[260px] [&>div:last-child]:min-h-[160px] [&>div:last-child]:text-xs"
                        isStreaming={runIsRunning}
                        output={runOutputDisplay}
                    />
                )}
            </CardContent>
        </Card>
    );
};
