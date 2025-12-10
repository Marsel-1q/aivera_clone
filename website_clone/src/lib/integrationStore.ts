import { promises as fs } from "fs";
import path from "path";

export type IntegrationPlatform = "telegram" | "whatsapp" | "google" | "slack";

export interface IntegrationConfig {
  platform: IntegrationPlatform;
  active: boolean;
  token?: string;
  updatedAt: number;
}

export interface CloneIntegrations {
  cloneId: string;
  integrations: IntegrationConfig[];
}

const STORAGE_PATH = path.resolve(process.cwd(), "uploads", "integrations.json");

// Simple mutex implementation to prevent race conditions
class SimpleMutex {
  private locked = false;
  private queue: (() => void)[] = [];

  async acquire(): Promise<() => void> {
    return new Promise((resolve) => {
      const tryAcquire = () => {
        if (!this.locked) {
          this.locked = true;
          resolve(() => this.release());
        } else {
          this.queue.push(tryAcquire);
        }
      };
      tryAcquire();
    });
  }

  private release() {
    this.locked = false;
    const next = this.queue.shift();
    if (next) next();
  }
}

const mutex = new SimpleMutex();

async function loadStore(): Promise<Record<string, CloneIntegrations>> {
  try {
    const content = await fs.readFile(STORAGE_PATH, "utf-8");
    const parsed = JSON.parse(content) as Record<string, CloneIntegrations>;
    return parsed || {};
  } catch {
    return {};
  }
}

async function saveStore(store: Record<string, CloneIntegrations>) {
  await fs.mkdir(path.dirname(STORAGE_PATH), { recursive: true });
  await fs.writeFile(STORAGE_PATH, JSON.stringify(store, null, 2), "utf-8");
}

export async function getIntegrations(cloneId: string): Promise<IntegrationConfig[]> {
  const release = await mutex.acquire();
  try {
    const store = await loadStore();
    const existing = store[cloneId];
    return existing?.integrations || [];
  } finally {
    release();
  }
}

export async function upsertIntegration(
  cloneId: string,
  platform: IntegrationPlatform,
  data: Partial<Pick<IntegrationConfig, "active" | "token">>
): Promise<IntegrationConfig[]> {
  const release = await mutex.acquire();
  try {
    const store = await loadStore();
    const now = Date.now();
    const record = store[cloneId] || { cloneId, integrations: [] as IntegrationConfig[] };
    const current = record.integrations.find((i) => i.platform === platform);
    if (current) {
      if (data.active !== undefined) current.active = data.active;
      if (data.token !== undefined) current.token = data.token;
      current.updatedAt = now;
    } else {
      record.integrations.push({
        platform,
        active: data.active ?? false,
        token: data.token,
        updatedAt: now,
      });
    }
    store[cloneId] = record;
    await saveStore(store);
    return record.integrations;
  } finally {
    release();
  }
}

export async function setIntegrations(cloneId: string, integrations: IntegrationConfig[]): Promise<IntegrationConfig[]> {
  const release = await mutex.acquire();
  try {
    const store = await loadStore();
    store[cloneId] = {
      cloneId,
      integrations: integrations.map((i) => ({ ...i, updatedAt: Date.now() })),
    };
    await saveStore(store);
    return store[cloneId].integrations;
  } finally {
    release();
  }
}
