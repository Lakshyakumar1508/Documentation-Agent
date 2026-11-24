/**
 * Data contracts and types for DocAgent VS Code integration.
 */

export interface APIRoute {
    http_method: string;
    path: string;
    handler_name: string;
    file_path: string;
    line_number: number;
}

export interface ConfigVariable {
    key: string;
    default_value?: string;
    is_secret: boolean;
    source_file: string;
}

export interface CodeInventory {
    repo_name: string;
    total_files: number;
    symbols_count: number;
    api_routes: APIRoute[];
    configs: ConfigVariable[];
}

export interface DocProposal {
    file_path: string;
    doc_type: string;
    original_content: string;
    proposed_content: string;
    unified_diff: string;
    rationale: string;
    is_new_file: boolean;
}

export interface ValidationFinding {
    rule: string;
    severity: "critical" | "warning" | "info";
    doc_file: string;
    line_number?: number;
    claim: string;
    message: string;
    suggested_fix?: string;
}

export interface ValidationReport {
    is_valid: boolean;
    critical_count: number;
    warning_count: number;
    findings: ValidationFinding[];
}

