import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

import { useShadowPortalRoot } from "@va/shared/contexts/use-shadow-portal-root";
import { cn } from "@va/shared/lib/utils";

function TooltipProvider({
    delayDuration = 0,
    ...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
    return (
        <TooltipPrimitive.Provider
            data-slot="tooltip-provider"
            delayDuration={delayDuration}
            {...props}
        />
    );
}

function Tooltip({
    ...props
}: React.ComponentProps<typeof TooltipPrimitive.Root>) {
    return (
        <TooltipProvider>
            <TooltipPrimitive.Root
                data-slot="tooltip"
                {...props}
            />
        </TooltipProvider>
    );
}

function TooltipTrigger({
    ...props
}: React.ComponentProps<typeof TooltipPrimitive.Trigger>) {
    return (
        <TooltipPrimitive.Trigger
            data-slot="tooltip-trigger"
            {...props}
        />
    );
}

function TooltipContent({
    className,
    sideOffset = 0,
    children,
    ...props
}: React.ComponentProps<typeof TooltipPrimitive.Content>) {
    const portalContainer = useShadowPortalRoot();

    return (
        <TooltipPrimitive.Portal
            container={portalContainer ?? undefined}
            data-slot="tooltip-portal"
        >
            <TooltipPrimitive.Content
                data-slot="tooltip-content"
                sideOffset={sideOffset}
                className={cn(
                    "bg-foreground text-background z-9999 w-fit origin-(--radix-tooltip-content-transform-origin) rounded-md px-3 py-1.5 text-xs text-balance",
                    className,
                )}
                {...props}
            >
                {children}
                <TooltipPrimitive.Arrow className="bg-foreground fill-foreground z-9999 size-2.5 translate-y-[calc(-50%_-_2px)] rotate-45 rounded-[2px]" />
            </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
    );
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
