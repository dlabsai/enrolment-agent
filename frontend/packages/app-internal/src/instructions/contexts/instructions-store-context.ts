import { createContext, use } from "react";
import { useStore } from "zustand";

import type {
    InstructionsActions,
    InstructionsStore,
    InstructionsStoreState,
} from "../lib/store";

export const InstructionsStoreContext = createContext<
    InstructionsStore | undefined
>(undefined);

const useInstructionsStoreContext = (): InstructionsStore => {
    const value = use(InstructionsStoreContext);
    if (value === undefined) {
        throw new Error("Missing InstructionsStoreProvider in the tree");
    }
    return value;
};

export const useInstructionsStore = <T>(
    selector: (state: InstructionsStoreState) => T,
): T => {
    const store = useInstructionsStoreContext();
    return useStore(store, selector);
};

/**
 * Get all actions.
 * Action references are stable, but this hook returns a new object each render.
 * Avoid using the returned object as a prop or effect dependency.
 */
export const useInstructionsActions = (): InstructionsActions => {
    const store = useInstructionsStoreContext();
    const state = store.getState();
    return {
        loadDiskTemplates: state.loadDiskTemplates,
        loadVersions: state.loadVersions,
        loadDeployedVersion: state.loadDeployedVersion,
        loadVersionDetail: state.loadVersionDetail,
        setActiveTab: state.setActiveTab,
        setActivePlatform: state.setActivePlatform,
        setActiveSection: state.setActiveSection,
        setSectionExpanded: state.setSectionExpanded,
        dismissGuide: state.dismissGuide,
        showGuidePanel: state.showGuidePanel,
        setError: state.setError,
        clearError: state.clearError,
        selectTemplate: state.selectTemplate,
        selectVersion: state.selectVersion,
        selectDefault: state.selectDefault,
        requestSelectVersion: state.requestSelectVersion,
        requestSelectDefault: state.requestSelectDefault,
        updateContent: state.updateContent,
        toggleDiff: state.toggleDiff,
        toggleWrapLines: state.toggleWrapLines,
        requestResetTemplate: state.requestResetTemplate,
        resetTemplate: state.resetTemplate,
        setVersionName: state.setVersionName,
        setVersionDescription: state.setVersionDescription,
        createVersion: state.createVersion,
        deployVersion: state.deployVersion,
        undeployVersion: state.undeployVersion,
        requestDeleteVersion: state.requestDeleteVersion,
        deleteVersion: state.deleteVersion,
        closeConfirmDialog: state.closeConfirmDialog,
        confirmAction: state.confirmAction,
        setTestChatVersion: state.setTestChatVersion,
        setTestChatChat: state.setTestChatChat,
        clearTestChat: state.clearTestChat,
        setChatPanelOpen: state.setChatPanelOpen,
        toggleChatPanel: state.toggleChatPanel,
        getBaseContent: state.getBaseContent,
    };
};

/**
 * Subscribe to store changes with a selector.
 * Returns the subscribe function from subscribeWithSelector middleware.
 */
export const useInstructionsStoreSubscribe =
    (): InstructionsStore["subscribe"] => {
        const store = useInstructionsStoreContext();
        return store.subscribe;
    };
