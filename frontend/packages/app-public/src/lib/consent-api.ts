import { ENVIRONMENT } from "@va/shared/config";
import {
    apiPost,
    handleFetchError,
    isApiError,
} from "@va/shared/lib/api-client";
import { logger } from "@va/shared/lib/logger";

import { MOCK_CONSENT_ENDPOINT } from "../config";
import {
    type ConsentData,
    getChatId,
    getConsentData,
    getUserId,
} from "./storage";

interface ConsentSubmissionPayload {
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    zip: string;
    conversation_id?: string;
    user_id: string;
    widget_closed?: boolean;
    environment: string;
}

export const submitConsentData = async (
    consentData: ConsentData,
    chatIds: string[],
    widgetClosed = false,
): Promise<{ success: boolean; error?: string }> => {
    if (MOCK_CONSENT_ENDPOINT) {
        logger.log(
            "Mock consent endpoint enabled - returning success without API call",
        );
        return { success: true };
    }

    try {
        const [chatId] = chatIds;
        const userId = getUserId();

        const payload: ConsentSubmissionPayload = {
            first_name: consentData.firstName,
            last_name: consentData.lastName,
            email: consentData.email,
            phone: consentData.phone,
            zip: consentData.zip,
            conversation_id: chatId,
            user_id: userId,
            environment: ENVIRONMENT,
            ...(widgetClosed && { widget_closed: true }),
        };

        logger.log("Submitting consent to backend:", payload);

        await apiPost<unknown>("/consent", payload);
        logger.log("Consent submitted successfully");
        return { success: true };
    } catch (error) {
        if (isApiError(error)) {
            return {
                success: false,
                error: error.detail,
            };
        }

        const errorMessage = handleFetchError(
            error,
            "Error submitting consent",
        );
        return {
            success: false,
            error: errorMessage,
        };
    }
};

export const submitConsentOnWidgetClose = async (): Promise<void> => {
    try {
        const consentData = getConsentData();
        if (consentData === undefined) {
            logger.log(
                "No consent data found, skipping widget close submission",
            );
            return;
        }

        const chatIds: string[] = [];
        const currentChatId = getChatId();
        if (currentChatId !== undefined && currentChatId !== "") {
            chatIds.push(currentChatId);
        }

        const result = await submitConsentData(consentData, chatIds, true);

        if (result.success) {
            logger.log("Widget close consent submitted successfully");
        } else {
            logger.error(
                "Failed to submit widget close consent:",
                result.error,
            );
        }
    } catch (error) {
        logger.error("Error in submitConsentOnWidgetClose:", error);
    }
};
