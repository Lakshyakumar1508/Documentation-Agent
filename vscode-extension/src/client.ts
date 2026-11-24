/**
 * Bridge client communicating with DocAgent CLI or REST API.
 */

import * as cp from "child_process";
import * as http from "http";
import * as path from "path";
import * as vscode from "vscode";
import { DocProposal, ValidationReport } from "./types";

export class DocAgentClient {
    private apiEndpoint: string;
    private useLocalCli: boolean;

    constructor() {
        const config = vscode.workspace.getConfiguration("docagent");
        this.apiEndpoint = config.get<string>("apiEndpoint", "http://127.0.0.1:8000");
        this.useLocalCli = config.get<boolean>("useLocalCLI", true);
    }

    /**
     * Executes 'docagent analyze' on the current workspace.
     */
    public async analyzeProject(workspaceRoot: string): Promise<string> {
        this.validatePathContainment(workspaceRoot);
        return this.executeCli(["analyze", "--path", workspaceRoot]);
    }

    /**
     * Executes 'docagent generate --yes' or queries the backend API.
     */
    public async generateDocs(workspaceRoot: string, autoApprove: boolean): Promise<string> {
        this.validatePathContainment(workspaceRoot);
        const args = ["generate", "--path", workspaceRoot];
        if (autoApprove) {
            args.push("--yes");
        }
        return this.executeCli(args);
    }

    /**
     * Executes 'docagent validate' to detect documentation drift.
     */
    public async checkDocumentation(workspaceRoot: string): Promise<string> {
        this.validatePathContainment(workspaceRoot);
        return this.executeCli(["validate", "--path", workspaceRoot]);
    }

    /**
     * Executes 'docagent logs <file>' to analyze error traces.
     */
    public async analyzeLogs(logPath: string): Promise<string> {
        return this.executeCli(["logs", logPath]);
    }

    /**
     * Executes CLI subprocess deterministically within workspace boundary.
     */
    private executeCli(args: string[]): Promise<string> {
        return new Promise((resolve, reject) => {
            // Locate python executable or docagent command
            const pythonPath = path.join(__dirname, "..", "..", ".venv", "Scripts", "python.exe");
            const cliArgs = ["-m", "docagent.cli.main", ...args];

            cp.execFile(pythonPath, cliArgs, { timeout: 30000 }, (error, stdout, stderr) => {
                if (error && error.code !== 0 && error.code !== 1) {
                    // Code 1 is returned when validation findings exist (valid business output)
                    reject(new Error(`CLI error: ${stderr || stdout || error.message}`));
                    return;
                }
                resolve(stdout || stderr);
            });
        });
    }

    /**
     * Prevents path traversal outside active workspace folders.
     */
    private validatePathContainment(targetPath: string): void {
        const folders = vscode.workspace.workspaceFolders;
        if (!folders || folders.length === 0) {
            throw new Error("No active workspace folder opened in VS Code.");
        }

        const resolvedTarget = path.resolve(targetPath);
        const isContained = folders.some((f) => {
            const resolvedRoot = path.resolve(f.uri.fsPath);
            return resolvedTarget.startsWith(resolvedRoot);
        });

        if (!isContained) {
            throw new Error(`Security Exception: Access denied for path outside workspace: ${targetPath}`);
        }
    }
}

