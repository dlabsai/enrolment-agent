import type { JSX } from "react";

import { PageHeader } from "../../components/page-header";
import { PageShell } from "../../components/page-shell";
import { SettingsPanel } from "./settings-panel";

export const SettingsPage = (): JSX.Element => (
    <PageShell variant="dashboard">
        <PageHeader title="Settings" />
        <SettingsPanel />
    </PageShell>
);
