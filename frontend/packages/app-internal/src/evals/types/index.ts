export type EvalSuite = "chatbot" | "guardrails" | "search";

export interface EvalReportSummary {
    id: string;
    name: string;
    generatedAt: string;
    repeats: number | null;
    concurrency: number | null;
    filename: string;
    sizeBytes: number;
}

export interface EvalReportDetail {
    id: string;
    name: string;
    generatedAt: string;
    repeats: number | null;
    concurrency: number | null;
    filename: string;
    sizeBytes: number;
    content: string;
}

export interface EvalRunRequest {
    suite: EvalSuite;
    repeat: number;
    maxConcurrency: number;
    passThreshold: number;
    testCases?: string;
    chatbotModel?: string;
    guardrailModel?: string;
    extractorModel?: string;
    evaluationModel?: string;
    searchModel?: string;
}

export interface EvalRunLogEntry {
    stream: "stdout" | "stderr" | "command";
    message: string;
}

export interface EvalRunStatusEvent {
    status: "start" | "complete" | "error" | "cancelled";
    exitCode?: number;
    logId?: string;
}

export interface EvalRunReportEvent {
    reportId: string;
    name: string;
    generatedAt: string;
    repeats: number | undefined;
    concurrency: number | undefined;
}

export interface EvalRunLogFile {
    id: string;
    filename: string;
    sizeBytes: number;
    content: string;
}

export interface EvalReportSummaryApi {
    id: string;
    name: string;
    generated_at: string;
    repeats: number | null;
    concurrency: number | null;
    filename: string;
    size_bytes: number;
}

export interface EvalReportDetailApi {
    id: string;
    name: string;
    generated_at: string;
    repeats: number | null;
    concurrency: number | null;
    filename: string;
    size_bytes: number;
    content: string;
}

export interface EvalRunLogFileApi {
    id: string;
    filename: string;
    size_bytes: number;
    content: string;
}

export interface EvalTestCasesApi {
    suite: EvalSuite;
    cases: string[];
}
