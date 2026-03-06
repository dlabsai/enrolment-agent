import { isRecord } from "@va/shared/lib/type-guards";

import type { AuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import type {
    EvalReportDetail,
    EvalReportDetailApi,
    EvalReportSummary,
    EvalReportSummaryApi,
    EvalRunLogEntry,
    EvalRunLogFile,
    EvalRunLogFileApi,
    EvalRunReportEvent,
    EvalRunRequest,
    EvalRunStatusEvent,
    EvalSuite,
    EvalTestCasesApi,
} from "../types";

const mapSummary = (report: EvalReportSummaryApi): EvalReportSummary => ({
    id: report.id,
    name: report.name,
    generatedAt: report.generated_at,
    repeats: report.repeats,
    concurrency: report.concurrency,
    filename: report.filename,
    sizeBytes: report.size_bytes,
});

const mapDetail = (report: EvalReportDetailApi): EvalReportDetail => ({
    id: report.id,
    name: report.name,
    generatedAt: report.generated_at,
    repeats: report.repeats,
    concurrency: report.concurrency,
    filename: report.filename,
    sizeBytes: report.size_bytes,
    content: report.content,
});

const mapRunLogFile = (logFile: EvalRunLogFileApi): EvalRunLogFile => ({
    id: logFile.id,
    filename: logFile.filename,
    sizeBytes: logFile.size_bytes,
    content: logFile.content,
});

interface EvalRunStreamCallbacks {
    onLog: (entry: EvalRunLogEntry) => void;
    onStatus: (status: EvalRunStatusEvent) => void;
    onReport: (report: EvalRunReportEvent) => void;
    onError: (message: string) => void;
}

const parseSseEvent = (
    raw: string,
): {
    event: string;
    data: string;
} => {
    let event = "message";
    const dataLines: string[] = [];

    for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
            event = line.slice("event:".length).trim();
        } else if (line.startsWith("data:")) {
            dataLines.push(line.slice("data:".length).trim());
        }
    }

    return {
        event,
        data: dataLines.join("\n"),
    };
};

const parseSsePayload = (data: string): Record<string, unknown> | undefined => {
    try {
        const parsed: unknown = JSON.parse(data);
        return isRecord(parsed) ? parsed : undefined;
    } catch {
        return undefined;
    }
};

const isEvalStatus = (value: unknown): value is EvalRunStatusEvent["status"] =>
    value === "start" ||
    value === "complete" ||
    value === "error" ||
    value === "cancelled";

export const fetchEvalReports = async (
    api: AuthenticatedApi,
): Promise<EvalReportSummary[]> => {
    const response = await api.get<EvalReportSummaryApi[]>("/evals/reports");
    return response.map((report) => mapSummary(report));
};

export const fetchEvalReport = async (
    api: AuthenticatedApi,
    reportId: string,
): Promise<EvalReportDetail> => {
    const response = await api.get<EvalReportDetailApi>(
        `/evals/reports/${encodeURIComponent(reportId)}`,
    );
    return mapDetail(response);
};

export const fetchEvalReportLog = async (
    api: AuthenticatedApi,
    reportId: string,
): Promise<EvalRunLogFile> => {
    const response = await api.get<EvalRunLogFileApi>(
        `/evals/reports/${encodeURIComponent(reportId)}/log`,
    );
    return mapRunLogFile(response);
};

export const fetchEvalTestCases = async (
    api: AuthenticatedApi,
    suite: EvalSuite,
): Promise<string[]> => {
    const response = await api.get<EvalTestCasesApi>(
        `/evals/test-cases?suite=${encodeURIComponent(suite)}`,
    );
    return response.cases;
};

export const fetchInternalModels = async (
    api: AuthenticatedApi,
): Promise<string[]> => api.get<string[]>("/models");

export const runEvalStream = async (
    api: AuthenticatedApi,
    request: EvalRunRequest,
    callbacks: EvalRunStreamCallbacks,
    signal?: AbortSignal,
): Promise<void> => {
    const response = await api.postStream(
        "/evals/runs/stream",
        {
            suite: request.suite,
            repeat: request.repeat,
            max_concurrency: request.maxConcurrency,
            pass_threshold: request.passThreshold,
            test_cases: request.testCases,
            chatbot_model: request.chatbotModel,
            guardrail_model: request.guardrailModel,
            extractor_model: request.extractorModel,
            evaluation_model: request.evaluationModel,
            search_model: request.searchModel,
        },
        { signal },
    );

    const reader = response.body?.getReader();

    if (reader === undefined) {
        throw new Error("Missing streaming response body");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        // eslint-disable-next-line no-await-in-loop
        const { value, done } = await reader.read();
        if (done) {
            break;
        }
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replaceAll("\r\n", "\n");

        let splitIndex = buffer.indexOf("\n\n");
        while (splitIndex !== -1) {
            const rawEvent = buffer.slice(0, splitIndex).trim();
            buffer = buffer.slice(splitIndex + 2);
            splitIndex = buffer.indexOf("\n\n");

            if (rawEvent !== "") {
                const parsed = parseSseEvent(rawEvent);
                if (parsed.data !== "") {
                    const payload = parseSsePayload(parsed.data);
                    if (payload !== undefined) {
                        switch (parsed.event) {
                            case "log": {
                                const { message, stream } = payload;
                                if (
                                    (stream === "stdout" ||
                                        stream === "stderr" ||
                                        stream === "command") &&
                                    typeof message === "string"
                                ) {
                                    callbacks.onLog({ stream, message });
                                }
                                break;
                            }
                            case "status": {
                                const {
                                    status: statusValue,
                                    exit_code: exitCode,
                                    log_id: logId,
                                } = payload;
                                if (isEvalStatus(statusValue)) {
                                    callbacks.onStatus({
                                        status: statusValue,
                                        exitCode:
                                            typeof exitCode === "number"
                                                ? exitCode
                                                : undefined,
                                        logId:
                                            typeof logId === "string"
                                                ? logId
                                                : undefined,
                                    });
                                }
                                break;
                            }
                            case "report": {
                                const {
                                    report_id: reportId,
                                    name,
                                    generated_at: generatedAt,
                                    repeats,
                                    concurrency,
                                } = payload;
                                if (
                                    typeof reportId === "string" &&
                                    typeof name === "string" &&
                                    typeof generatedAt === "string"
                                ) {
                                    callbacks.onReport({
                                        reportId,
                                        name,
                                        generatedAt,
                                        repeats:
                                            typeof repeats === "number"
                                                ? repeats
                                                : undefined,
                                        concurrency:
                                            typeof concurrency === "number"
                                                ? concurrency
                                                : undefined,
                                    });
                                }
                                break;
                            }
                            case "error": {
                                const { message } = payload;
                                if (typeof message === "string") {
                                    callbacks.onError(message);
                                }
                                break;
                            }
                            default: {
                                break;
                            }
                        }
                    }
                }
            }
        }
    }
};
