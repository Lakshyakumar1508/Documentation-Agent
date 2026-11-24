/**
 * Documentation Agent - Official VS Code Extension Entry Point.
 */

import * as vscode from "vscode";
import { DocAgentClient } from "./client";

let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel("Documentation Agent");
    const client = new DocAgentClient();

    // Helper to get primary workspace path
    const getWorkspacePath = (): string => {
        const folders = vscode.workspace.workspaceFolders;
        if (!folders || folders.length === 0) {
            throw new Error("Please open a workspace folder to run Documentation Agent.");
        }
        return folders[0].uri.fsPath;
    };

    // 1. Command: Analyze Project
    const analyzeCommand = vscode.commands.registerCommand("docagent.analyzeProject", async () => {
        try {
            const root = getWorkspacePath();
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: "Documentation Agent: Scanning Code AST & APIs...",
                    cancellable: false,
                },
                async () => {
                    const output = await client.analyzeProject(root);
                    outputChannel.clear();
                    outputChannel.appendLine(output);
                    outputChannel.show(true);
                }
            );
            vscode.window.showInformationMessage("Project analysis completed. See output channel for details.");
        } catch (error: any) {
            vscode.window.showErrorMessage(`Analysis failed: ${error.message}`);
        }
    });

    // 2. Command: Generate README
    const generateCommand = vscode.commands.registerCommand("docagent.generateReadme", async () => {
        try {
            const root = getWorkspacePath();
            const config = vscode.workspace.getConfiguration("docagent");
            const autoApprove = config.get<boolean>("autoApprove", false);

            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: "Documentation Agent: Generating Grounded Documentation...",
                    cancellable: false,
                },
                async () => {
                    const output = await client.generateDocs(root, autoApprove);
                    outputChannel.clear();
                    outputChannel.appendLine(output);
                    outputChannel.show(true);
                }
            );

            // Open README.md if it exists
            const readmeUri = vscode.Uri.file(`${root}/README.md`);
            try {
                await vscode.workspace.fs.stat(readmeUri);
                const doc = await vscode.workspace.openTextDocument(readmeUri);
                await vscode.window.showTextDocument(doc, { preview: false });
            } catch {
                // Ignore if not created yet
            }

            vscode.window.showInformationMessage("Documentation generation finished.");
        } catch (error: any) {
            vscode.window.showErrorMessage(`Generation failed: ${error.message}`);
        }
    });

    // 3. Command: Check Documentation (Drift Detector)
    const checkCommand = vscode.commands.registerCommand("docagent.checkDocumentation", async () => {
        try {
            const root = getWorkspacePath();
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: "Documentation Agent: Verifying Documentation Claims...",
                    cancellable: false,
                },
                async () => {
                    const output = await client.checkDocumentation(root);
                    outputChannel.clear();
                    outputChannel.appendLine(output);
                    outputChannel.show(true);

                    if (output.includes("CRITICAL")) {
                        vscode.window.showWarningMessage(
                            "Documentation Drift Detected: Some claims contradict the active codebase. See output for details."
                        );
                    } else {
                        vscode.window.showInformationMessage("All documentation claims verified against source code!");
                    }
                }
            );
        } catch (error: any) {
            vscode.window.showErrorMessage(`Consistency check failed: ${error.message}`);
        }
    });

    // 4. Command: Analyze Logs
    const analyzeLogsCommand = vscode.commands.registerCommand("docagent.analyzeLogs", async () => {
        try {
            const fileUri = await vscode.window.showOpenDialog({
                canSelectFiles: true,
                canSelectFolders: false,
                canSelectMany: false,
                openLabel: "Select Log File",
                filters: {
                    "Log Files": ["log", "txt", "out"],
                    "All Files": ["*"],
                },
            });

            if (!fileUri || fileUri.length === 0) {
                return;
            }

            const logPath = fileUri[0].fsPath;
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: "Documentation Agent: Clustering Log Errors & Traces...",
                    cancellable: false,
                },
                async () => {
                    const output = await client.analyzeLogs(logPath);
                    outputChannel.clear();
                    outputChannel.appendLine(output);
                    outputChannel.show(true);
                }
            );
            vscode.window.showInformationMessage("Log analysis complete. See output channel for error clusters.");
        } catch (error: any) {
            vscode.window.showErrorMessage(`Log analysis failed: ${error.message}`);
        }
    });

    // 5. Command: Review Changes
    const reviewChangesCommand = vscode.commands.registerCommand("docagent.reviewChanges", async () => {
        try {
            const root = getWorkspacePath();
            const choice = await vscode.window.showQuickPick(
                [
                    { label: "Accept All Proposed Changes", description: "Apply generated documentation to workspace files" },
                    { label: "Run Fresh Consistency Check", description: "Scan workspace and verify documentation claims" },
                ],
                { placeHolder: "Select DocAgent Review Action" }
            );

            if (!choice) {
                return;
            }

            if (choice.label.startsWith("Accept")) {
                await client.generateDocs(root, true);
                vscode.window.showInformationMessage("Approved changes have been applied to workspace files.");
            } else {
                vscode.commands.executeCommand("docagent.checkDocumentation");
            }
        } catch (error: any) {
            vscode.window.showErrorMessage(`Review failed: ${error.message}`);
        }
    });

    context.subscriptions.push(
        analyzeCommand,
        generateCommand,
        checkCommand,
        analyzeLogsCommand,
        reviewChangesCommand,
        outputChannel
    );
}

export function deactivate() {
    if (outputChannel) {
        outputChannel.dispose();
    }
}

