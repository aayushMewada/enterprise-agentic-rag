const { spawnSync } = require("child_process");
const path = require("path");

const isWindows = process.platform === "win32";
const repoRoot = path.resolve(__dirname, "..");
const pythonPath = isWindows
  ? path.join(repoRoot, "venv", "Scripts", "python.exe")
  : path.join(repoRoot, "venv", "bin", "python");

const result = spawnSync(
  pythonPath,
  ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
  {
    cwd: repoRoot,
    stdio: "inherit",
    shell: false,
    env: {
      ...process.env,
      HF_HUB_OFFLINE: process.env.HF_HUB_OFFLINE || "1",
      TRANSFORMERS_OFFLINE: process.env.TRANSFORMERS_OFFLINE || "1",
    },
  }
);

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
