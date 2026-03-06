import type { Root } from "react-dom/client";

declare global {
    interface HTMLElement {
        __chatWidgetRoot?: Root;
    }
}
