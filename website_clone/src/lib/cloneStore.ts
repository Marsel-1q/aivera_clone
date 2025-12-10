import { randomUUID } from "crypto";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import path from "path";

export type CloneStatus = "training" | "ready" | "failed";

export interface KnowledgeSource {
  source: string; // original path (may be full path)
  chunks: number;
  displayName?: string; // human-friendly file name
  size?: number; // bytes
}

export interface CloneRecord {
  id: string;
  name: string;
  modelId: string;
  jobId: string;
  status: CloneStatus;
  datasetCount?: number;
  datasetId?: string;
  messengers?: string[];
  apiKey?: string;
  isRunning?: boolean;
  startedAt?: number;
  createdAt: number;
  updatedAt: number;
  knowledgeCount?: number;
  knowledgeSources?: KnowledgeSource[];
  knowledgeFile?: string;
  ragIndexDir?: string;
}

// Persistent storage path
const STORAGE_DIR = path.resolve(process.cwd(), "uploads", "data");
const CLONES_FILE = path.join(STORAGE_DIR, "clones.json");

// Debounce save to avoid excessive writes
let saveTimeout: ReturnType<typeof setTimeout> | null = null;
const SAVE_DEBOUNCE_MS = 500;

function ensureStorageDir() {
  if (!existsSync(STORAGE_DIR)) {
    mkdirSync(STORAGE_DIR, { recursive: true });
  }
}

function loadClonesFromDisk(): Map<string, CloneRecord> {
  ensureStorageDir();
  if (!existsSync(CLONES_FILE)) {
    // Return default demo clone if no file exists
    const now = Date.now();
    return new Map<string, CloneRecord>([
      ["demo-clones", {
        id: "demo-clones",
        name: "CyberClone Alpha",
        modelId: "llama-3-8b-instruct",
        jobId: "job-888",
        status: "ready",
        datasetCount: 12,
        datasetId: "demo-dataset",
        messengers: ["telegram", "whatsapp", "discord"],
        apiKey: "sk-live-demo-key-12345",
        isRunning: false, // Reset running state on load
        startedAt: now,
        createdAt: now,
        updatedAt: now,
        knowledgeCount: 2,
        knowledgeSources: [
          { source: "demo/knowledge/about_product.md", chunks: 1 },
          { source: "demo/knowledge/faq.md", chunks: 1 },
        ],
        knowledgeFile: "uploads/jobs/job-888/processed_dataset/knowledge.jsonl",
        ragIndexDir: "uploads/jobs/job-888/rag_index",
      }]
    ]);
  }

  try {
    const content = readFileSync(CLONES_FILE, "utf-8");
    const parsed = JSON.parse(content) as Record<string, CloneRecord>;
    const map = new Map<string, CloneRecord>();
    for (const [id, clone] of Object.entries(parsed)) {
      // Reset isRunning on load - workers are not running after restart
      clone.isRunning = false;
      map.set(id, clone);
    }
    console.log(`[cloneStore] Loaded ${map.size} clones from disk`);
    return map;
  } catch (err) {
    console.error("[cloneStore] Failed to load clones from disk:", err);
    return new Map();
  }
}

function saveClonesToDisk() {
  ensureStorageDir();
  try {
    const obj: Record<string, CloneRecord> = {};
    for (const [id, clone] of clones) {
      obj[id] = clone;
    }
    writeFileSync(CLONES_FILE, JSON.stringify(obj, null, 2), "utf-8");
  } catch (err) {
    console.error("[cloneStore] Failed to save clones to disk:", err);
  }
}

function scheduleSave() {
  if (saveTimeout) {
    clearTimeout(saveTimeout);
  }
  saveTimeout = setTimeout(() => {
    saveClonesToDisk();
    saveTimeout = null;
  }, SAVE_DEBOUNCE_MS);
}

// Initialize from disk on module load
const clones = loadClonesFromDisk();

export function createClone(params: {
  name: string;
  modelId: string;
  jobId: string;
  status?: CloneStatus;
  datasetCount?: number;
  datasetId?: string;
  startedAt?: number;
  knowledgeCount?: number;
  knowledgeSources?: KnowledgeSource[];
  knowledgeFile?: string;
  ragIndexDir?: string;
}): CloneRecord {
  const id = randomUUID();
  const now = Date.now();
  const clone: CloneRecord = {
    id,
    name: params.name,
    modelId: params.modelId,
    jobId: params.jobId,
    status: params.status || "training",
    datasetCount: params.datasetCount,
    datasetId: params.datasetId,
    messengers: [], // Default empty
    apiKey: randomUUID().replace(/-/g, ""), // Generate simple API key
    isRunning: false,
    startedAt: params.startedAt ?? now,
    knowledgeCount: params.knowledgeCount,
    knowledgeSources: params.knowledgeSources,
    knowledgeFile: params.knowledgeFile,
    ragIndexDir: params.ragIndexDir,
    createdAt: now,
    updatedAt: now,
  };
  clones.set(id, clone);
  scheduleSave();
  return clone;
}

export function updateClone(
  id: string,
  data: Partial<
    Pick<
      CloneRecord,
      "status" | "updatedAt" | "name" | "isRunning" | "messengers" | "datasetCount" | "datasetId" | "knowledgeCount" | "knowledgeSources" | "knowledgeFile" | "ragIndexDir"
    >
  >
) {
  const clone = clones.get(id);
  if (!clone) return undefined;
  if (data.status) clone.status = data.status;
  if (data.name) clone.name = data.name;
  if (data.isRunning !== undefined) clone.isRunning = data.isRunning;
  if (data.messengers) clone.messengers = data.messengers;
  if (data.datasetCount !== undefined) clone.datasetCount = data.datasetCount;
  if (data.datasetId) clone.datasetId = data.datasetId;
  // allow clearing/overwriting knowledge info
  if (data.knowledgeCount !== undefined) clone.knowledgeCount = data.knowledgeCount;
  if (data.knowledgeSources !== undefined) clone.knowledgeSources = data.knowledgeSources;
  if (data.knowledgeFile !== undefined) clone.knowledgeFile = data.knowledgeFile;
  if (data.ragIndexDir !== undefined) clone.ragIndexDir = data.ragIndexDir;

  clone.updatedAt = data.updatedAt ?? Date.now();
  clones.set(id, clone);
  scheduleSave();
  return clone;
}

export function listClones(): CloneRecord[] {
  return Array.from(clones.values());
}

export function getClone(id: string): CloneRecord | undefined {
  return clones.get(id);
}

// Force immediate save (useful for critical operations)
export function forceSave() {
  if (saveTimeout) {
    clearTimeout(saveTimeout);
    saveTimeout = null;
  }
  saveClonesToDisk();
}
