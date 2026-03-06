import { cn } from "@va/shared/lib/utils";
import type { JSX, ReactNode } from "react";

type PageShellVariant = "dashboard" | "workspace" | "centered";

interface PageShellProps {
    children: ReactNode;
    className?: string;
    variant?: PageShellVariant;
}

const variantStyles: Record<PageShellVariant, string> = {
    dashboard: "@container/main flex flex-1 flex-col gap-4 overflow-auto py-4",
    workspace: "flex h-full min-h-0 min-w-0 flex-1 overflow-hidden",
    centered: "@container/main flex flex-1 flex-col gap-4 overflow-auto py-4",
};

export const PageShell = ({
    children,
    className,
    variant = "dashboard",
}: PageShellProps): JSX.Element => (
    <div className={cn(variantStyles[variant], className)}>{children}</div>
);

interface PageSectionProps {
    children: ReactNode;
    className?: string;
}

export const PageSection = ({
    children,
    className,
}: PageSectionProps): JSX.Element => (
    <div className={cn("px-4 lg:px-6", className)}>{children}</div>
);
