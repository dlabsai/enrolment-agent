export const VISIBLE_BY_DEFAULT =
    String(import.meta.env.VITE_VISIBLE_BY_DEFAULT ?? "") === "yes";

export const MOCK_CONSENT_ENDPOINT =
    String(import.meta.env.VITE_MOCK_CONSENT_ENDPOINT ?? "") === "yes";
