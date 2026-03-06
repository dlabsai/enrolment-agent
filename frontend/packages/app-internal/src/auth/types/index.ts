export interface UserProfile {
    id: string;
    email: string;
    name: string;
    role: "user" | "admin" | "dev";
    is_active: boolean;
    created_at: string;
    updated_at: string;
}
