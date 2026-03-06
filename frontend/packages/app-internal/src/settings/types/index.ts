export interface AppSettingsResponse {
    effective: Record<string, string>;
    system: Record<string, string>;
    overrides: Record<string, string>;
}

export interface AppSettingsUpdate {
    university_name?: string | null;
    university_website_url?: string | null;
    university_admissions_phone?: string | null;
    university_transcripts_email?: string | null;
    university_application_url?: string | null;
    university_accreditation_url?: string | null;
    guardrails_blocked_message?: string | null;
}
