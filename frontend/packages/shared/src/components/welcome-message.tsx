import type { JSX } from "react";

export const WelcomeMessage = (): JSX.Element => (
    <div className="p-4 text-left">
        <h2 className="text-primary mb-2 text-3xl font-bold">Welcome!</h2>
        <p className="text-primary text-lg">How can I help you today?</p>
    </div>
);
