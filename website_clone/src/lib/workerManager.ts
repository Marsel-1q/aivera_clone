import path from "path";
import { fork, ChildProcess } from "child_process";
import { existsSync, mkdirSync, writeFileSync, readFileSync, unlinkSync, readdirSync } from "fs";
import { getClone, updateClone } from "./cloneStore";
import { getJob } from "./jobStore";
import { getIntegrations } from "./integrationStore";

type WorkerStatus = "starting" | "running" | "stopped" | "error";

interface WorkerRecord {
  child: ChildProcess;
  status: WorkerStatus;
  lastHeartbeat: number;
  pid: number;
}

// PID files directory for tracking workers across restarts
const PID_DIR = path.resolve(process.cwd(), "uploads", "pids");

function ensurePidDir() {
  if (!existsSync(PID_DIR)) {
    mkdirSync(PID_DIR, { recursive: true });
  }
}

function getPidFilePath(cloneId: string): string {
  return path.join(PID_DIR, `worker-${cloneId}.pid`);
}

function savePidFile(cloneId: string, pid: number) {
  ensurePidDir();
  writeFileSync(getPidFilePath(cloneId), String(pid), "utf-8");
}

function removePidFile(cloneId: string) {
  const pidFile = getPidFilePath(cloneId);
  if (existsSync(pidFile)) {
    try {
      unlinkSync(pidFile);
    } catch (err) {
      console.error(`[workerManager] Failed to remove PID file for ${cloneId}:`, err);
    }
  }
}

function readPidFile(cloneId: string): number | null {
  const pidFile = getPidFilePath(cloneId);
  if (!existsSync(pidFile)) return null;
  try {
    const content = readFileSync(pidFile, "utf-8").trim();
    return parseInt(content, 10);
  } catch {
    return null;
  }
}

function isProcessRunning(pid: number): boolean {
  try {
    process.kill(pid, 0); // Signal 0 just checks if process exists
    return true;
  } catch {
    return false;
  }
}

function killProcess(pid: number) {
  try {
    process.kill(pid, "SIGTERM");
    console.log(`[workerManager] Sent SIGTERM to process ${pid}`);
    // Give it time to gracefully shutdown
    setTimeout(() => {
      try {
        if (isProcessRunning(pid)) {
          process.kill(pid, "SIGKILL");
          console.log(`[workerManager] Sent SIGKILL to process ${pid}`);
        }
      } catch { /* Process already dead */ }
    }, 3000);
  } catch (err) {
    console.log(`[workerManager] Process ${pid} already dead or inaccessible`);
  }
}

const workers = new Map<string, WorkerRecord>();

// Heartbeat monitoring interval
const HEARTBEAT_TIMEOUT_MS = 20000; // 20 seconds without heartbeat
let monitoringInterval: ReturnType<typeof setInterval> | null = null;

function startHeartbeatMonitoring() {
  if (monitoringInterval) return;

  monitoringInterval = setInterval(() => {
    const now = Date.now();
    for (const [cloneId, record] of workers) {
      if (record.status === "running" && now - record.lastHeartbeat > HEARTBEAT_TIMEOUT_MS) {
        console.warn(`[workerManager] Worker ${cloneId} timed out, marking as error`);
        record.status = "error";
        updateClone(cloneId, { status: "failed", isRunning: false });
        // Don't kill - let it die naturally or recover
      }
    }
  }, 10000);
}

export function getWorkerStatus(cloneId: string): { status: WorkerStatus; lastHeartbeat?: number; pid?: number } | null {
  const rec = workers.get(cloneId);
  if (!rec) return null;
  return { status: rec.status, lastHeartbeat: rec.lastHeartbeat, pid: rec.pid };
}

/**
 * Clean up orphaned workers on server startup.
 * Call this once when the server starts.
 */
export async function cleanupOrphanedWorkers() {
  ensurePidDir();
  const files = readdirSync(PID_DIR).filter(f => f.startsWith("worker-") && f.endsWith(".pid"));

  for (const file of files) {
    const cloneId = file.replace("worker-", "").replace(".pid", "");
    const pid = readPidFile(cloneId);

    if (pid && isProcessRunning(pid)) {
      console.log(`[workerManager] Killing orphaned worker for clone ${cloneId} (PID: ${pid})`);
      killProcess(pid);
    }

    removePidFile(cloneId);
  }

  console.log(`[workerManager] Cleaned up ${files.length} orphaned worker PID files`);
}

export async function startCloneWorker(cloneId: string) {
  // Check if worker already running in memory
  if (workers.has(cloneId)) {
    return { ok: false, error: "Worker already running" };
  }

  // Check and kill any orphaned process from before
  const existingPid = readPidFile(cloneId);
  if (existingPid && isProcessRunning(existingPid)) {
    console.log(`[workerManager] Killing existing worker process ${existingPid} for clone ${cloneId}`);
    killProcess(existingPid);
    removePidFile(cloneId);
    // Wait a bit for cleanup
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  const clone = getClone(cloneId);
  if (!clone) return { ok: false, error: "Clone not found" };
  const job = getJob(clone.jobId);
  const integrations = await getIntegrations(cloneId);

  const scriptPath = path.resolve(process.cwd(), "scripts", "clone_worker.js");
  const child = fork(scriptPath, [], {
    env: {
      ...process.env,
      CLONE_ID: cloneId,
      MODEL_ID: clone.modelId,
      ADAPTER_DIR: job?.adapterDir || "",
      RAG_INDEX_DIR: job?.ragIndexDir || "",
      SYSTEM_PROMPT: job?.systemPrompt || "",
      INTEGRATIONS: JSON.stringify(integrations),
      CLONE_API_URL: process.env.CLONE_API_URL || "http://localhost:3000",
    },
  });

  const pid = child.pid!;
  savePidFile(cloneId, pid);

  const record: WorkerRecord = { child, status: "starting", lastHeartbeat: Date.now(), pid };
  workers.set(cloneId, record);
  updateClone(cloneId, { isRunning: true, status: "ready" });

  // Start monitoring if not already
  startHeartbeatMonitoring();

  child.on("message", (msg: any) => {
    if (msg?.type === "heartbeat") {
      record.status = "running";
      record.lastHeartbeat = Date.now();
    }
    if (msg?.type === "ready") {
      record.status = "running";
    }
    if (msg?.type === "error") {
      record.status = "error";
      updateClone(cloneId, { status: "failed", isRunning: false });
    }
  });

  child.on("exit", (code) => {
    console.log(`[workerManager] Worker ${cloneId} exited with code ${code}`);
    workers.delete(cloneId);
    removePidFile(cloneId);
    updateClone(cloneId, { isRunning: false });
  });

  child.on("error", (err) => {
    console.error(`[workerManager] Worker ${cloneId} error:`, err);
    record.status = "error";
    updateClone(cloneId, { status: "failed", isRunning: false });
  });

  return { ok: true, pid };
}

export function stopCloneWorker(cloneId: string) {
  const rec = workers.get(cloneId);
  if (!rec) {
    // Maybe orphaned - try to kill via PID file
    const pid = readPidFile(cloneId);
    if (pid && isProcessRunning(pid)) {
      killProcess(pid);
      removePidFile(cloneId);
      updateClone(cloneId, { isRunning: false });
      return { ok: true, wasOrphaned: true };
    }
    return { ok: false, error: "Worker not running" };
  }

  try {
    rec.child.kill("SIGTERM");
    workers.delete(cloneId);
    removePidFile(cloneId);
    updateClone(cloneId, { isRunning: false });
    return { ok: true };
  } catch (err: any) {
    return { ok: false, error: err?.message || String(err) };
  }
}

export function listRunningWorkers(): { cloneId: string; status: WorkerStatus; pid: number }[] {
  const result: { cloneId: string; status: WorkerStatus; pid: number }[] = [];
  for (const [cloneId, record] of workers) {
    result.push({ cloneId, status: record.status, pid: record.pid });
  }
  return result;
}

