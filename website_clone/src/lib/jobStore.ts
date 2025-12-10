import { randomUUID } from "crypto";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import path from "path";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface TrainingJob {
  id: string;
  modelId: string;
  datasetPath: string;
  systemPrompt: string;
  persona?: string;
  cloneId?: string;
  cloneName?: string;
  adapterDir?: string;
  processedDir?: string;
  knowledgeFile?: string;
  ragIndexDir?: string;
  knowledgeCount?: number;
  knowledgeSources?: { source: string; chunks: number; displayName?: string; size?: number }[];
  createdAt: number;
  updatedAt: number;
  status: JobStatus;
  logs: string[];
  error?: string;
}

// Persistent storage path
const STORAGE_DIR = path.resolve(process.cwd(), "uploads", "data");
const JOBS_FILE = path.join(STORAGE_DIR, "jobs.json");

// Debounce save to avoid excessive writes
let saveTimeout: ReturnType<typeof setTimeout> | null = null;
const SAVE_DEBOUNCE_MS = 500;

function ensureStorageDir() {
  if (!existsSync(STORAGE_DIR)) {
    mkdirSync(STORAGE_DIR, { recursive: true });
  }
}

function loadJobsFromDisk(): Map<string, TrainingJob> {
  ensureStorageDir();
  if (!existsSync(JOBS_FILE)) {
    return new Map();
  }

  try {
    const content = readFileSync(JOBS_FILE, "utf-8");
    const parsed = JSON.parse(content) as Record<string, TrainingJob>;
    const map = new Map<string, TrainingJob>();
    for (const [id, job] of Object.entries(parsed)) {
      // Reset running jobs to failed on restart (they were interrupted)
      if (job.status === "running") {
        job.status = "failed";
        job.error = "Training interrupted by server restart";
      }
      map.set(id, job);
    }
    console.log(`[jobStore] Loaded ${map.size} jobs from disk`);
    return map;
  } catch (err) {
    console.error("[jobStore] Failed to load jobs from disk:", err);
    return new Map();
  }
}

function saveJobsToDisk() {
  ensureStorageDir();
  try {
    const obj: Record<string, TrainingJob> = {};
    for (const [id, job] of jobs) {
      obj[id] = job;
    }
    writeFileSync(JOBS_FILE, JSON.stringify(obj, null, 2), "utf-8");
  } catch (err) {
    console.error("[jobStore] Failed to save jobs to disk:", err);
  }
}

function scheduleSave() {
  if (saveTimeout) {
    clearTimeout(saveTimeout);
  }
  saveTimeout = setTimeout(() => {
    saveJobsToDisk();
    saveTimeout = null;
  }, SAVE_DEBOUNCE_MS);
}

// Initialize from disk on module load
const jobs = loadJobsFromDisk();

export function createJob(params: {
  modelId: string;
  datasetPath: string;
  systemPrompt: string;
  persona?: string;
  cloneId?: string;
  cloneName?: string;
  adapterDir?: string;
}): TrainingJob {
  const id = randomUUID();
  const now = Date.now();
  const job: TrainingJob = {
    id,
    modelId: params.modelId,
    datasetPath: params.datasetPath,
    systemPrompt: params.systemPrompt,
    persona: params.persona,
    cloneId: params.cloneId,
    cloneName: params.cloneName,
    adapterDir: params.adapterDir,
    createdAt: now,
    updatedAt: now,
    status: "queued",
    logs: [],
  };
  jobs.set(id, job);
  scheduleSave();
  return job;
}

export function updateJob(
  id: string,
  data: Partial<
    Pick<
      TrainingJob,
      "status" | "logs" | "error" | "updatedAt" | "adapterDir" | "processedDir" | "knowledgeFile" | "ragIndexDir" | "knowledgeCount" | "knowledgeSources"
    >
  >
): TrainingJob | undefined {
  const job = jobs.get(id);
  if (!job) return undefined;
  if (data.status) job.status = data.status;
  if (data.logs) job.logs = data.logs;
  if (data.error) job.error = data.error;
  if (data.adapterDir) job.adapterDir = data.adapterDir;
  if (data.processedDir) job.processedDir = data.processedDir;
  if (data.knowledgeFile !== undefined) job.knowledgeFile = data.knowledgeFile;
  if (data.ragIndexDir !== undefined) job.ragIndexDir = data.ragIndexDir;
  if (data.knowledgeCount !== undefined) job.knowledgeCount = data.knowledgeCount;
  if (data.knowledgeSources !== undefined) job.knowledgeSources = data.knowledgeSources;
  job.updatedAt = data.updatedAt ?? Date.now();
  jobs.set(id, job);
  scheduleSave();
  return job;
}

export function getJob(id: string): TrainingJob | undefined {
  return jobs.get(id);
}

export function appendLog(id: string, line: string) {
  const job = jobs.get(id);
  if (!job) return;
  job.logs.push(line);
  job.updatedAt = Date.now();
  scheduleSave();
}

export function listJobs(): TrainingJob[] {
  return Array.from(jobs.values());
}

// Force immediate save (useful for critical operations)
export function forceSave() {
  if (saveTimeout) {
    clearTimeout(saveTimeout);
    saveTimeout = null;
  }
  saveJobsToDisk();
}
