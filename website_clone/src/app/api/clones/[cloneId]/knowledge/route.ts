import { NextResponse } from "next/server";
import path from "path";
import { promises as fs, existsSync } from "fs";
import { spawn } from "child_process";
import { getClone, updateCloneRepo } from "@/lib/repositories/cloneRepository";
import { getJob, updateJobRepo } from "@/lib/repositories/jobRepository";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
// export const dynamic = "force-dynamic"; // Not strictly needed for POST/DELETE if strictly defined, but harmless

const REPO_ROOT = path.resolve(process.cwd(), "..");
const DATASETS_DIR = path.resolve(process.cwd(), "uploads", "datasets");
const JOBS_DIR = path.resolve(process.cwd(), "uploads", "jobs");

type KnowledgeSource = {
  source: string;
  chunks: number;
  displayName?: string;
  size?: number;
};

function runLogged(command: string, args: string[], opts: Parameters<typeof spawn>[2]): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, opts);
    proc.stdout.on("data", (d) => console.log("[knowledge]", d.toString()));
    proc.stderr.on("data", (d) => console.warn("[knowledge]", d.toString()));
    proc.on("close", (code) => {
      if (code !== 0) reject(new Error(`${command} exited with code ${code}`));
      else resolve();
    });
  });
}

async function readKnowledgeStats(knowledgeFile: string): Promise<{ totalChunks: number; sources: KnowledgeSource[] }> {
  try {
    const exists = await fs.stat(knowledgeFile).then(() => true).catch(() => false);
    if (!exists) return { totalChunks: 0, sources: [] };
    const content = await fs.readFile(knowledgeFile, "utf-8");
    const lines = content.split("\n").filter(Boolean);
    const counters: Record<string, KnowledgeSource> = {};
    for (const line of lines) {
      try {
        const parsed = JSON.parse(line);
        const source = (parsed?.source as string | undefined) || "unknown";
        const displayName = path.basename(source);
        if (!counters[source]) {
          let size: number | undefined;
          try {
            const stat = await fs.stat(source);
            size = stat.size;
          } catch {
            size = undefined;
          }
          counters[source] = { source, displayName, size, chunks: 0 };
        }
        counters[source].chunks += 1;
      } catch {
        continue;
      }
    }
    const sources = Object.values(counters);
    const totalChunks = sources.reduce((acc, item) => acc + item.chunks, 0);
    return { totalChunks, sources };
  } catch (err) {
    console.error("Failed to read knowledge stats:", err);
    return { totalChunks: 0, sources: [] };
  }
}

async function rebuildIndex(knowledgeFile: string, ragIndexDir: string) {
  await runLogged(
    "python3",
    ["-m", "rag.index_builder", "--knowledge-file", knowledgeFile, "--output-dir", ragIndexDir],
    { cwd: REPO_ROOT, env: { ...process.env, PYTHONPATH: [REPO_ROOT, process.env.PYTHONPATH || ""].filter(Boolean).join(":") } }
  );
}

// Rerun pipeline is mostly for populating knowledge.jsonl initially, typically handled by training job.
// But we keep it here if "reprocess" is needed.
async function rerunPipeline(datasetId: string, processedDir: string, persona: string) {
  await fs.mkdir(processedDir, { recursive: true }).catch(() => { });
  const cliPath = path.join(REPO_ROOT, "dataset_pipeline", "cli.py");
  const args = [
    cliPath,
    "--inputs",
    path.join(DATASETS_DIR, datasetId),
    "--output-dir",
    processedDir,
    "--persona",
    persona || "user_persona",
    "--format",
    "huggingface",
    "--eval-split",
    "0.1",
  ];
  await runLogged(
    "python3",
    args,
    { cwd: REPO_ROOT, env: { ...process.env, PYTHONPATH: [REPO_ROOT, process.env.PYTHONPATH || ""].filter(Boolean).join(":") } }
  );
}

async function updateState(
  cloneId: string,
  jobId: string | undefined, // Note: jobId might be just an ID string, verify logic
  knowledgeFile: string,
  ragIndexDir: string
) {
  const stats = await readKnowledgeStats(knowledgeFile);

  // Update Clone via Repository
  await updateCloneRepo(cloneId, {
    knowledgeSources: stats.sources,
    knowledgeCount: stats.totalChunks,
    knowledgeFile,
    ragIndexDir,
  });

  // Update Job via Repository if it exists and matches
  if (jobId) {
    // We assume jobId is a valid string if present.
    // However, updateJobRepo expects the ID.
    try {
      await updateJobRepo(jobId, {
        knowledgeSources: stats.sources,
        knowledgeCount: stats.totalChunks,
        knowledgeFile,
        ragIndexDir,
      });
    } catch (e) {
      console.warn("Failed to update related job:", e);
    }
  }
  return stats;
}

export async function POST(
  request: Request,
  props: { params: Promise<{ cloneId: string }> }
) {
  const params = await props.params;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { cloneId } = params;
  const clone = await getClone(cloneId);
  if (!clone) return NextResponse.json({ error: "Clone not found" }, { status: 404 });
  if (clone.userId && clone.userId !== user.id) return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  if (!clone.datasetId) return NextResponse.json({ error: "Clone has no dataset" }, { status: 400 });

  // Resolve Job
  let job: any = undefined;
  if (clone.jobId) {
    try {
      job = await getJob(clone.jobId);
    } catch (err) { console.warn("Job not found", err); }
  }

  // Determine paths
  const jobRoot = clone.jobId ? path.join(JOBS_DIR, clone.jobId) : path.join(JOBS_DIR, "adhoc");
  const processedDir = job?.processedDir || path.join(jobRoot, "processed_dataset");
  const knowledgeFile = clone.knowledgeFile || path.join(processedDir, "knowledge.jsonl");
  const ragIndexDir = clone.ragIndexDir || path.join(jobRoot, "rag_index");
  const persona = job?.persona || "user_persona";

  try {
    // 1. Reprocess dataset to refresh knowledge.jsonl from source files
    await rerunPipeline(clone.datasetId, processedDir, persona);

    // 2. Rebuild RAG index
    await rebuildIndex(knowledgeFile, ragIndexDir);

    // 3. Update DB
    const stats = await updateState(cloneId, clone.jobId, knowledgeFile, ragIndexDir);

    // Return fresh clone data
    const freshClone = await getClone(cloneId);
    return NextResponse.json({
      success: true,
      knowledgeSources: stats.sources,
      knowledgeCount: stats.totalChunks,
      clone: freshClone
    });
  } catch (err: any) {
    console.error("Rebuild failed:", err);
    return NextResponse.json({ error: err?.message || String(err) }, { status: 500 });
  }
}

export async function DELETE(
  request: Request,
  props: { params: Promise<{ cloneId: string }> }
) {
  const params = await props.params;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { cloneId } = params;
  const clone = await getClone(cloneId); // Uses Supabase Repository
  if (!clone) {
    return NextResponse.json({ error: "Clone not found" }, { status: 404 });
  }
  // Optional: check ownership
  // The repository (getClone) usually bypasses RLS if using service role, or respects it if using auth client?
  // Our repositories use `createClient()` from server.ts which uses cookies, so it respects RLS.
  // But just in case, double check:
  // (Wait, Repository `getClone` returns a plain object. RLS at DB level ensures we only get it if we own it,
  // OR if we are admin. Since we use `createClient()` with cookies, RLS should handle it. 
  // If `getClone` returns null, it's either not there or not yours.)

  const body = await request.json().catch(() => null);
  const filename = body?.filename || body?.source;
  console.log(`[knowledge:DELETE] cloneId=${cloneId}, filename=${filename}`);
  if (!filename) {
    return NextResponse.json({ error: "filename is required" }, { status: 400 });
  }

  // Resolve directories
  // We need to know where the knowledge file is.
  let job: any = undefined;
  if (clone.jobId) {
    job = await getJob(clone.jobId);
  }
  const jobRoot = clone.jobId ? path.join(JOBS_DIR, clone.jobId) : path.join(JOBS_DIR, "adhoc");
  const processedDir = job?.processedDir || path.join(jobRoot, "processed_dataset");
  const knowledgeFile = clone.knowledgeFile || path.join(processedDir, "knowledge.jsonl");
  const ragIndexDir = clone.ragIndexDir || path.join(jobRoot, "rag_index");

  // 1. Delete physical file from dataset ONLY IF it exists
  if (clone.datasetId) {
    const targetDir = path.join(DATASETS_DIR, clone.datasetId);
    const targetPath = path.join(targetDir, path.basename(filename));

    // Safety check: ensure targetPath is within DATASETS_DIR to prevent traversal
    if (!targetPath.startsWith(DATASETS_DIR)) {
      return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
    }

    try {
      if (existsSync(targetPath)) {
        await fs.unlink(targetPath);
        console.log(`[knowledge:DELETE] File deleted: ${targetPath}`);
      } else {
        console.warn(`[knowledge:DELETE] File not found: ${targetPath}`);
      }
    } catch (err: any) {
      console.error("Delete file failed:", err);
      return NextResponse.json({ error: `Failed to delete file: ${err?.message}` }, { status: 500 });
    }
  }

  // 2. Remove entries from knowledge.jsonl
  try {
    const exists = await fs.stat(knowledgeFile).then(() => true).catch(() => false);
    if (exists) {
      const content = await fs.readFile(knowledgeFile, "utf-8");
      if (content) {
        const lines = content.split("\n").filter(Boolean);
        const filtered = lines.filter((line) => {
          try {
            const parsed = JSON.parse(line);
            const src = (parsed?.source as string | undefined) || "";
            // Compare basenames to be safe
            return path.basename(src) !== path.basename(filename);
          } catch {
            return true;
          }
        });
        await fs.writeFile(knowledgeFile, filtered.map((l) => l + "\n").join(""), "utf-8");
      }
    }
  } catch (err) {
    console.warn("Failed to filter knowledge file:", err);
  }

  // 3. Rebuild RAG Index
  let stats = await readKnowledgeStats(knowledgeFile);
  if (stats.totalChunks > 0) {
    try {
      await rebuildIndex(knowledgeFile, ragIndexDir);
      stats = await readKnowledgeStats(knowledgeFile); // reread safely
    } catch (err) {
      console.warn("RAG rebuild failed after delete:", err);
    }
  } else {
    // If empty, remove the index dir entirely
    await fs.rm(ragIndexDir, { recursive: true, force: true }).catch(() => { });
  }

  // 4. Update DB State
  const finalRagIndexDir = stats.totalChunks > 0 ? ragIndexDir : ""; // Store empty string or null instead of undefined if using partial?
  // Actually, repo handles undefined.

  await updateCloneRepo(cloneId, {
    knowledgeSources: stats.sources,
    knowledgeCount: stats.totalChunks,
    knowledgeFile,
    ragIndexDir: stats.totalChunks > 0 ? ragIndexDir : undefined, // pass undefined to NOT update, or handle logic for clearing? 
    // If we want to CLEAR it in DB, we need to pass explicit null if repo supports it, 
    // or just leave it since an empty index dir path is still valid context (just empty).
    // Let's keep the path, just the count is 0.
  });

  if (clone.jobId) {
    await updateJobRepo(clone.jobId, {
      knowledgeSources: stats.sources,
      knowledgeCount: stats.totalChunks,
      knowledgeFile, // keep path
    });
  }

  const updatedClone = await getClone(cloneId);
  return NextResponse.json({
    success: true,
    knowledgeSources: stats.sources,
    knowledgeCount: stats.totalChunks,
    clone: updatedClone,
  });
}
