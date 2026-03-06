import { logger } from "@va/shared/lib/logger";
import { isRecord } from "@va/shared/lib/type-guards";
import type { ChatMessage } from "@va/shared/types";

const CHAT_HISTORY_KEY = "chat_history";
const CONSENT_KEY = "chat_consent_given";
const CONSENT_DATA_KEY = "chat_consent_data";
const CONSENT_CHAT_IDS_KEY = "chat_consent_chat_ids";
const USER_ID_KEY = "chat_user_id";

interface StoredChatHistory {
    messages: ChatMessage[];
    chatId?: string;
    parentMessageId?: string;
}

const isValidStoredChatHistory = (
    value: unknown,
): value is StoredChatHistory => {
    if (!isRecord(value)) {
        return false;
    }

    if (!Array.isArray(value.messages)) {
        return false;
    }

    return true;
};

const getStoredChatHistory = (): StoredChatHistory | undefined => {
    try {
        const raw = localStorage.getItem(CHAT_HISTORY_KEY) ?? undefined;
        if (raw === undefined) {
            return undefined;
        }

        const parsed: unknown = JSON.parse(raw) ?? undefined;
        if (!isValidStoredChatHistory(parsed)) {
            logger.warn("Invalid chat history format in storage");
            return undefined;
        }

        return parsed;
    } catch (error) {
        logger.error("Error reading chat history from storage:", error);
        return undefined;
    }
};

const saveStoredChatHistory = (history: StoredChatHistory): boolean => {
    try {
        localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history));
        return true;
    } catch (error) {
        logger.error("Error saving chat history to storage:", error);
        return false;
    }
};

const updateStoredChatHistoryField = <K extends keyof StoredChatHistory>(
    field: K,
    value: StoredChatHistory[K],
): void => {
    const history = getStoredChatHistory();
    if (history === undefined) {
        const newHistory: StoredChatHistory = { messages: [], [field]: value };
        saveStoredChatHistory(newHistory);
    } else {
        history[field] = value;
        saveStoredChatHistory(history);
    }
};

export const createChatHistory = (): void => {
    try {
        const localChatHistory =
            localStorage.getItem(CHAT_HISTORY_KEY) ?? undefined;
        if (localChatHistory !== undefined) {
            try {
                const parsed: unknown =
                    JSON.parse(localChatHistory) ?? undefined;
                if (parsed !== undefined && typeof parsed === "object") {
                    return;
                }
            } catch {
                logger.warn("Found invalid chat history, recreating");
            }
        }

        const storedChatHistory: StoredChatHistory = {
            messages: [],
        };
        localStorage.setItem(
            CHAT_HISTORY_KEY,
            JSON.stringify(storedChatHistory),
        );
    } catch (error) {
        logger.error("Error creating chat history:", error);
    }
};

export const fetchChatHistory = (): ChatMessage[] => {
    const history = getStoredChatHistory();
    if (history === undefined) {
        return [];
    }
    return history.messages;
};

export const updateStoredHistory = (message: ChatMessage): void => {
    const messageWithTimestamp: ChatMessage = {
        ...message,
        timestamp: message.timestamp,
    };

    const existing = getStoredChatHistory();
    const history = existing ?? { messages: [] };
    history.messages.push(messageWithTimestamp);
    saveStoredChatHistory(history);
};

export const getChatId = (): string | undefined => {
    const history = getStoredChatHistory();
    return history?.chatId ?? undefined;
};

export const setChatId = (chatId: string): void => {
    updateStoredChatHistoryField("chatId", chatId);
};

export const getParentMessageId = (): string | undefined => {
    const history = getStoredChatHistory();
    return history?.parentMessageId ?? undefined;
};

export const setParentMessageId = (parentMessageId: string): void => {
    updateStoredChatHistoryField("parentMessageId", parentMessageId);
};

export interface ConsentData {
    firstName: string;
    lastName: string;
    email: string;
    phone: string;
    zip: string;
    timestamp: number;
}

export const hasCompleteConsentData = (): boolean => {
    try {
        const consent = localStorage.getItem(CONSENT_KEY);
        if (consent !== "true") {
            return false;
        }

        const consentDataStr =
            localStorage.getItem(CONSENT_DATA_KEY) ?? undefined;
        if (consentDataStr === undefined || consentDataStr === "") {
            logger.warn("Consent data is missing");
            return false;
        }

        try {
            const consentData: unknown =
                JSON.parse(consentDataStr) ?? undefined;
            if (!isRecord(consentData)) {
                logger.warn("Consent data is invalid");
                return false;
            }

            const requiredFields: (keyof ConsentData)[] = [
                "firstName",
                "lastName",
                "email",
                "phone",
                "zip",
                "timestamp",
            ];
            for (const field of requiredFields) {
                if (!(field in consentData)) {
                    logger.warn(
                        `Consent data missing required field: ${field}`,
                    );
                    return false;
                }
            }
        } catch (parseError) {
            logger.warn("Failed to parse consent data:", parseError);
            return false;
        }

        const userId = localStorage.getItem(USER_ID_KEY) ?? undefined;
        if (userId === undefined || userId === "") {
            logger.warn("User ID is missing");
            return false;
        }

        return true;
    } catch (error) {
        logger.error("Error checking complete consent data:", error);
        return false;
    }
};

export const setConsent = (value: boolean): void => {
    try {
        localStorage.setItem(CONSENT_KEY, value.toString());
    } catch (error) {
        logger.error("Error setting consent:", error);
    }
};

export const setConsentData = (data: ConsentData): void => {
    try {
        localStorage.setItem(CONSENT_DATA_KEY, JSON.stringify(data));
    } catch (error) {
        logger.error("Error setting consent data:", error);
    }
};

const isValidConsentData = (value: unknown): value is ConsentData => {
    if (!isRecord(value)) {
        return false;
    }
    return (
        "firstName" in value &&
        typeof value.firstName === "string" &&
        "lastName" in value &&
        typeof value.lastName === "string" &&
        "email" in value &&
        typeof value.email === "string" &&
        "phone" in value &&
        typeof value.phone === "string" &&
        "zip" in value &&
        typeof value.zip === "string" &&
        "timestamp" in value &&
        typeof value.timestamp === "number"
    );
};

export const getConsentData = (): ConsentData | undefined => {
    try {
        const raw = localStorage.getItem(CONSENT_DATA_KEY) ?? undefined;
        if (raw === undefined) {
            return undefined;
        }
        const parsed: unknown = JSON.parse(raw) ?? undefined;
        return isValidConsentData(parsed) ? parsed : undefined;
    } catch (error) {
        logger.error("Error getting consent data:", error);
        return undefined;
    }
};

const isStringArray = (value: unknown): value is string[] =>
    Array.isArray(value) && value.every((item) => typeof item === "string");

const getStoredConsentChatIds = (): string[] => {
    const stored = localStorage.getItem(CONSENT_CHAT_IDS_KEY) ?? undefined;
    if (stored === undefined) {
        return [];
    }
    const parsed: unknown = JSON.parse(stored) ?? undefined;
    return isStringArray(parsed) ? parsed : [];
};

export const addConsentChatId = (chatId: string): void => {
    try {
        const ids = getStoredConsentChatIds();
        if (!ids.includes(chatId)) {
            ids.push(chatId);
            localStorage.setItem(CONSENT_CHAT_IDS_KEY, JSON.stringify(ids));
        }
    } catch (error) {
        logger.error("Error adding consent chat ID:", error);
    }
};

export const getConsentChatIds = (): string[] => {
    try {
        return getStoredConsentChatIds();
    } catch (error) {
        logger.error("Error getting consent chat IDs:", error);
        return [];
    }
};

const generateUUID = (): string => crypto.randomUUID();

export const getUserId = (): string => {
    try {
        const existingUserId = localStorage.getItem(USER_ID_KEY) ?? undefined;
        if (existingUserId !== undefined) {
            return existingUserId;
        }

        const newUserId = generateUUID();
        localStorage.setItem(USER_ID_KEY, newUserId);
        return newUserId;
    } catch (error) {
        logger.error("Error getting/setting user ID:", error);
        return generateUUID();
    }
};
