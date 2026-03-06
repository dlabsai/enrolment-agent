import { ADMISSIONS_PHONE, ADMISSIONS_PHONE_TEL } from "@va/shared/config";
import { Phone } from "lucide-react";
import type { JSX } from "react";

export const Footer = (): JSX.Element => (
    <div className="text-muted-foreground px-4 pt-0 pb-3 text-sm">
        <p
            aria-label="Direct assistance contact information"
            className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center leading-relaxed"
            role="note"
        >
            <span className="inline-flex items-center gap-2 whitespace-nowrap">
                <Phone
                    aria-hidden="true"
                    className="size-4 shrink-0"
                />
                <a
                    className="text-primary font-semibold underline-offset-2 hover:underline"
                    href={`tel:${ADMISSIONS_PHONE_TEL}`}
                >
                    {ADMISSIONS_PHONE}
                </a>
            </span>
            <span>
                or{" "}
                <button
                    className="text-primary cursor-pointer border-0 bg-transparent p-0 font-semibold underline-offset-2 hover:underline"
                    onClick={() => {
                        // TODO: handle this
                    }}
                    type="button"
                >
                    chat with our advisor
                </button>
                .
            </span>
        </p>
    </div>
);
