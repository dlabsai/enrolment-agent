import { StreamLanguage } from "@codemirror/language";
import { jinja2 } from "@codemirror/legacy-modes/mode/jinja2";
import { EditorView } from "@codemirror/view";
import { githubDark, githubLight } from "@uiw/codemirror-theme-github";
import CodeMirror from "@uiw/react-codemirror";
import { FileText } from "lucide-react";
import { type JSX, useMemo } from "react";
import CodeMirrorMerge from "react-codemirror-merge";

import { useDarkMode } from "../../lib/hooks/use-dark-mode";
import {
    useInstructionsActions,
    useInstructionsStore,
} from "../contexts/instructions-store-context";
import { EditorToolbar } from "./editor-toolbar";
import { VersionDetailView } from "./version-detail-view";

const jinja2Language = StreamLanguage.define(jinja2);

const EmptyState = (): JSX.Element => (
    <div className="text-muted-foreground flex flex-1 items-center justify-center">
        <div className="text-center">
            <FileText className="mx-auto size-12 opacity-40" />
            <p className="mt-2 font-medium">Select instructions to edit</p>
            <p className="mt-1 text-sm opacity-70">
                Choose instructions from the sidebar
            </p>
        </div>
    </div>
);

const CodeEditor = (): JSX.Element => {
    const editedContent = useInstructionsStore((state) => state.editedContent);
    const wrapLines = useInstructionsStore((state) => state.wrapLines);
    const editorKey = useInstructionsStore((state) => state.editorKey);

    const { updateContent } = useInstructionsActions();

    const isDarkMode = useDarkMode();

    const editorExtensions = useMemo(
        () =>
            wrapLines
                ? [jinja2Language, EditorView.lineWrapping]
                : [jinja2Language],
        [wrapLines],
    );

    const handleChange = (value: string): void => {
        updateContent(value);
    };

    return (
        <CodeMirror
            basicSetup={{
                lineNumbers: true,
                highlightActiveLineGutter: true,
                highlightActiveLine: true,
                foldGutter: true,
                bracketMatching: true,
                indentOnInput: true,
            }}
            className="h-full [&_.cm-editor]:h-full [&_.cm-scroller]:overflow-auto"
            extensions={editorExtensions}
            height="100%"
            key={editorKey}
            onChange={handleChange}
            theme={isDarkMode ? githubDark : githubLight}
            value={editedContent}
        />
    );
};

const DiffEditor = (): JSX.Element => {
    const editedContent = useInstructionsStore((state) => state.editedContent);
    const selectedTemplate = useInstructionsStore(
        (state) => state.selectedTemplate,
    );
    const diskTemplates = useInstructionsStore((state) => state.diskTemplates);
    const wrapLines = useInstructionsStore((state) => state.wrapLines);
    const editorKey = useInstructionsStore((state) => state.editorKey);

    const { updateContent } = useInstructionsActions();

    const isDarkMode = useDarkMode();

    const editorExtensions = useMemo(
        () =>
            wrapLines
                ? [jinja2Language, EditorView.lineWrapping]
                : [jinja2Language],
        [wrapLines],
    );

    const originalContent = useMemo(() => {
        if (selectedTemplate === undefined) {
            return "";
        }
        const template = diskTemplates.find(
            (template) => template.filename === selectedTemplate,
        );
        return template?.content ?? "";
    }, [selectedTemplate, diskTemplates]);

    const handleChange = (value: string): void => {
        updateContent(value);
    };

    return (
        <CodeMirrorMerge
            className="h-full [&_.cm-editor]:h-full [&_.cm-mergeView]:h-full [&_.cm-scroller]:overflow-auto"
            collapseUnchanged={{
                margin: 3,
                minSize: 4,
            }}
            key={editorKey}
            revertControls="a-to-b"
            theme={isDarkMode ? githubDark : githubLight}
        >
            <CodeMirrorMerge.Original
                extensions={editorExtensions}
                readOnly
                value={originalContent}
            />
            <CodeMirrorMerge.Modified
                extensions={editorExtensions}
                onChange={handleChange}
                value={editedContent}
            />
        </CodeMirrorMerge>
    );
};

const TemplateEditor = (): JSX.Element => {
    const showDiff = useInstructionsStore((state) => state.showDiff);

    return (
        <div className="flex-1 overflow-hidden">
            {showDiff ? <DiffEditor /> : <CodeEditor />}
        </div>
    );
};

export const EditorArea = (): JSX.Element => {
    const selectedTemplate = useInstructionsStore(
        (state) => state.selectedTemplate,
    );
    const selectedVersionDetail = useInstructionsStore(
        (state) => state.selectedVersionDetail,
    );

    return (
        <div className="flex flex-1 flex-col overflow-hidden">
            <EditorToolbar />
            {selectedTemplate === undefined ? (
                selectedVersionDetail === undefined ? (
                    <EmptyState />
                ) : (
                    <VersionDetailView />
                )
            ) : (
                <TemplateEditor />
            )}
        </div>
    );
};
