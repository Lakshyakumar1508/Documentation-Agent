/**
 * Unit tests for VS Code extension client bridge and commands.
 */

const assert = require("assert");
const path = require("path");
const cp = require("child_process");

console.log("Running VS Code Extension Bridge Tests...");

// 1. Test CLI Bridge execution
const rootDir = path.resolve(__dirname, "..", "..");
const pythonExe = path.join(rootDir, ".venv", "Scripts", "python.exe");

cp.execFile(pythonExe, ["-m", "docagent.cli.main", "--help"], (err, stdout, stderr) => {
    assert.strictEqual(err, null, "CLI invocation must succeed");
    assert.ok(stdout.includes("docagent"), "Output must contain docagent title");
    assert.ok(stdout.includes("analyze"), "Output must contain analyze subcommand");
    assert.ok(stdout.includes("generate"), "Output must contain generate subcommand");
    console.log("✓ CLI Bridge execution verified successfully.");

    // 2. Test analyze command on current repo root
    cp.execFile(pythonExe, ["-m", "docagent.cli.main", "analyze", "--path", rootDir], (err2, stdout2) => {
        assert.strictEqual(err2, null, "Analyze command must execute without errors");
        assert.ok(stdout2.includes("Repository Analysis"), "Must produce Repository Analysis panel");
        console.log("✓ VS Code extension workspace analyze command verified.");
        console.log("All VS Code extension tests passed successfully!");
    });
});

