import { cn } from "@va/shared/lib/utils";
import type { JSX, ReactNode } from "react";

interface PageHeaderProps {
    title: string;
    children?: ReactNode;
    className?: string;
}

export const PageHeader = ({
    title,
    children,
    className,
}: PageHeaderProps): JSX.Element => (
    <div
        className={cn(
            "flex flex-wrap items-center justify-between gap-3 px-4 lg:px-6",
            className,
        )}
    >
        <h2 className="text-lg font-semibold">{title}</h2>
        {children !== undefined && (
            <div className="flex flex-wrap items-center gap-2">{children}</div>
        )}
    </div>
);

interface PageHeaderGroupProps {
    label?: string;
    children: ReactNode;
    className?: string;
}

export const PageHeaderGroup = ({
    label,
    children,
    className,
}: PageHeaderGroupProps): JSX.Element => (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
        {label !== undefined && (
            <span className="text-muted-foreground text-xs">{label}</span>
        )}
        {children}
    </div>
);
