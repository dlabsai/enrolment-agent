import type { AuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import type { AppSettingsResponse, AppSettingsUpdate } from "../types";

export const fetchSettings = async (
    api: AuthenticatedApi,
): Promise<AppSettingsResponse> => api.get<AppSettingsResponse>("/settings");

export const updateSettings = async (
    api: AuthenticatedApi,
    updates: AppSettingsUpdate,
): Promise<AppSettingsResponse> =>
    api.post<AppSettingsResponse>("/settings", updates);

export const resetSettings = async (
    api: AuthenticatedApi,
): Promise<AppSettingsResponse> =>
    api
        .delete("/settings")
        .then(async () => api.get<AppSettingsResponse>("/settings"));
