const { spawnSync } = require("child_process");
const path = require("path");

const isWindows = process.platform === "win32";
const repoRoot = path.resolve(__dirname, "..");
const pythonPath = isWindows
  ? path.join(repoRoot, "venv", "Scripts", "python.exe")
  : path.join(repoRoot, "venv", "bin", "python");

const args = process.argv.slice(2);

if (args.length === 0) {
  console.error("Usage: node scripts/run-python.js <script> [args...]");
  process.exit(1);
}

const result = spawnSync(pythonPath, args, {
  cwd: repoRoot,
  stdio: "inherit",
  shell: false,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
