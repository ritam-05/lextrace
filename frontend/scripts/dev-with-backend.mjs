import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawn } from "node:child_process";
import http from "node:http";

const frontendRoot = process.cwd();
const repoRoot = resolve(frontendRoot, "..");
const nextBin = resolve(frontendRoot, "node_modules", ".bin", process.platform === "win32" ? "next.cmd" : "next");
const venvPython = resolve(repoRoot, "venv", "Scripts", "python.exe");
const backendPython = process.env.BACKEND_PYTHON || (existsSync(venvPython) ? venvPython : "python");
const backendHost = process.env.BACKEND_HOST || "127.0.0.1";
const backendPort = process.env.BACKEND_PORT || "8000";
const backendBaseUrl = process.env.FASTAPI_BASE_URL || `http://${backendHost}:${backendPort}`;

let backendProcess = null;
let nextProcess = null;
let ownsBackend = false;

function prefixStream(stream, prefix, writer = process.stdout) {
  stream.on("data", (chunk) => {
    const text = chunk.toString();
    for (const line of text.split(/\r?\n/)) {
      if (line.length > 0) {
        writer.write(`${prefix} ${line}\n`);
      }
    }
  });
}

function spawnNextDev() {
  if (process.platform === "win32") {
    return spawn("cmd.exe", ["/c", nextBin, "dev"], {
      cwd: frontendRoot,
      env: {
        ...process.env,
        FASTAPI_BASE_URL: backendBaseUrl,
      },
      stdio: "inherit",
    });
  }

  return spawn(nextBin, ["dev"], {
    cwd: frontendRoot,
    env: {
      ...process.env,
      FASTAPI_BASE_URL: backendBaseUrl,
    },
    stdio: "inherit",
  });
}

function isBackendHealthy() {
  return new Promise((resolveHealthy) => {
    const request = http.get(`${backendBaseUrl}/health`, (response) => {
      response.resume();
      resolveHealthy(response.statusCode === 200);
    });

    request.on("error", () => resolveHealthy(false));
    request.setTimeout(1500, () => {
      request.destroy();
      resolveHealthy(false);
    });
  });
}

async function waitForBackend(timeoutMs = 120000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (backendProcess?.exitCode !== null && backendProcess?.exitCode !== undefined) {
      throw new Error(`Backend exited early with code ${backendProcess.exitCode}`);
    }

    if (await isBackendHealthy()) {
      return;
    }

    await new Promise((resolveSleep) => setTimeout(resolveSleep, 1500));
  }

  throw new Error("Backend did not become healthy in time.");
}

function shutdown(code = 0) {
  if (nextProcess && nextProcess.exitCode === null) {
    nextProcess.kill("SIGINT");
  }
  if (ownsBackend && backendProcess && backendProcess.exitCode === null) {
    backendProcess.kill("SIGINT");
  }
  process.exit(code);
}

async function main() {
  if (!existsSync(nextBin)) {
    throw new Error("Next.js binary not found. Run npm install in frontend first.");
  }

  process.env.FASTAPI_BASE_URL = backendBaseUrl;
  if (await isBackendHealthy()) {
    process.stdout.write(`[dev] Reusing existing backend at ${backendBaseUrl}\n`);
  } else {
    const backendArgs = [
      "-m",
      "uvicorn",
      "backend.app:app",
      "--host",
      backendHost,
      "--port",
      backendPort,
      "--reload",
    ];

    backendProcess = spawn(backendPython, backendArgs, {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    ownsBackend = true;

    prefixStream(backendProcess.stdout, "[backend]");
    prefixStream(backendProcess.stderr, "[backend]", process.stderr);

    backendProcess.on("exit", (code) => {
      if (nextProcess && nextProcess.exitCode === null) {
        process.stderr.write(`\n[backend] exited with code ${code}\n`);
        nextProcess.kill("SIGINT");
      }
    });

    process.stdout.write(`[dev] Starting backend at ${backendBaseUrl}\n`);
    await waitForBackend();
  }

  process.stdout.write("[dev] Backend is healthy. Starting frontend.\n");

  nextProcess = spawnNextDev();

  nextProcess.on("error", (error) => {
    process.stderr.write(
      `[dev] Frontend process failed to start: ${error instanceof Error ? error.message : String(error)}\n`
    );
    if (ownsBackend && backendProcess && backendProcess.exitCode === null) {
      backendProcess.kill("SIGINT");
    }
    process.exit(1);
  });

  nextProcess.on("exit", (code) => {
    if (ownsBackend && backendProcess && backendProcess.exitCode === null) {
      backendProcess.kill("SIGINT");
    }
    process.exit(code ?? 0);
  });
}

process.on("SIGINT", () => shutdown(130));
process.on("SIGTERM", () => shutdown(143));

main().catch((error) => {
  process.stderr.write(`[dev] ${error instanceof Error ? error.message : String(error)}\n`);
  shutdown(1);
});
