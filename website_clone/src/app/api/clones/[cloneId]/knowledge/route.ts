import { NextResponse } from "next/server";
import path from "path";
import { promises as fs, existsSync } from "fs";
import { spawn } from "child_process";
import { getClone, updateClone } from "@/lib/cloneStore";
import { getJob, updateJob } from "@/lib/jobStore";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

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
  jobId: string | undefined,
  knowledgeFile: string,
  ragIndexDir: string
) {
  const stats = await readKnowledgeStats(knowledgeFile);
  updateClone(cloneId, {
    knowledgeSources: stats.sources,
    knowledgeCount: stats.totalChunks,
    knowledgeFile,
    ragIndexDir,
  });
  if (jobId) {
    updateJob(jobId, {
      knowledgeSources: stats.sources,
      knowledgeCount: stats.totalChunks,
      knowledgeFile,
      ragIndexDir,
    });
  }
  return stats;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ cloneId: string }> }
) {
  const { cloneId } = await params;
  const clone = getClone(cloneId);
  if (!clone) return NextResponse.json({ error: "Clone not found" }, { status: 404 });
  if (!clone.datasetId) return NextResponse.json({ error: "Clone has no dataset" }, { status: 400 });

  const job = clone.jobId ? getJob(clone.jobId) : undefined;
  const jobRoot = clone.jobId ? path.join(JOBS_DIR, clone.jobId) : path.join(JOBS_DIR, "adhoc");
  const processedDir = job?.processedDir || path.join(jobRoot, "processed_dataset");
  const knowledgeFile = clone.knowledgeFile || path.join(processedDir, "knowledge.jsonl");
  const ragIndexDir = clone.ragIndexDir || path.join(jobRoot, "rag_index");
  const persona = job?.persona || "user_persona";

  try {
    await rerunPipeline(clone.datasetId, processedDir, persona);
    await rebuildIndex(knowledgeFile, ragIndexDir);
    const stats = await updateState(cloneId, clone.jobId, knowledgeFile, ragIndexDir);
    return NextResponse.json({ success: true, knowledgeSources: stats.sources, knowledgeCount: stats.totalChunks, clone: getClone(cloneId) });
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || String(err) }, { status: 500 });
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ cloneId: string }> }
) {
  const { cloneId } = await params;
  const clone = getClone(cloneId);
  if (!clone) {
    return NextResponse.json({ error: "Clone not found" }, { status: 404 });
  }

  const body = await request.json().catch(() => null);
  const filename = body?.filename || body?.source;
  console.log(`[knowledge:DELETE] cloneId=${cloneId}, filename=${filename}`);
  if (!filename) {
    return NextResponse.json({ error: "filename is required" }, { status: 400 });
  }
  /* 
  if (!clone.datasetId) {
    return NextResponse.json({ error: "Clone has no dataset" }, { status: 400 });
  } 
  */

  const job = clone.jobId ? getJob(clone.jobId) : undefined;
  const jobRoot = clone.jobId ? path.join(JOBS_DIR, clone.jobId) : path.join(JOBS_DIR, "adhoc");
  const processedDir = job?.processedDir || path.join(jobRoot, "processed_dataset");
  const knowledgeFile = clone.knowledgeFile || path.join(processedDir, "knowledge.jsonl");
  const ragIndexDir = clone.ragIndexDir || path.join(jobRoot, "rag_index");

  // Only attempt file deletion if datasetId is known
  if (clone.datasetId) {
    const targetDir = path.join(DATASETS_DIR, clone.datasetId);
    const targetPath = path.join(targetDir, path.basename(filename));
    console.log(`[knowledge:DELETE] targetPath=${targetPath}, exists=${existsSync(targetPath)}`);

    try {
      await fs.unlink(targetPath);
      console.log(`[knowledge:DELETE] File deleted: ${targetPath}`);
    } catch (err: any) {
      // If file is already gone, continue; otherwise surface error
      if (err?.code !== "ENOENT") {
        return NextResponse.json({ error: `Failed to delete file: ${err?.message || err}` }, { status: 500 });
      }
    }
  } else {
    console.warn(`[knowledge:DELETE] Missing datasetId for clone ${cloneId}. Skipping file deletion, but cleaning knowledge index.`);
  }

  // Filter knowledge file to exclude deleted source
  try {
    const content = await fs.readFile(knowledgeFile, "utf-8").catch(() => "");
    if (content) {
      const lines = content.split("\n").filter(Boolean);
      const filtered = lines.filter((line) => {
        try {
          const parsed = JSON.parse(line);
          const src = (parsed?.source as string | undefined) || "";
          return path.basename(src) !== path.basename(filename);
        } catch {
          return true;
        }
      });
      await fs.writeFile(knowledgeFile, filtered.map((l) => l + "\n").join(""), "utf-8");
    }
  } catch (err) {
    console.warn("Failed to filter knowledge file:", err);
  }

  // Rebuild or clear index
  let stats = await readKnowledgeStats(knowledgeFile);
  if (stats.totalChunks > 0) {
    try {
      await rebuildIndex(knowledgeFile, ragIndexDir);
      stats = await readKnowledgeStats(knowledgeFile);
    } catch (err) {
      console.warn("RAG rebuild failed after delete:", err);
    }
  } else {
    // remove empty knowledge/index
    await fs.rm(ragIndexDir, { recursive: true, force: true }).catch(() => { });
  }

  updateClone(cloneId, {
    knowledgeSources: stats.sources,
    knowledgeCount: stats.totalChunks,
    knowledgeFile,
    ragIndexDir: stats.totalChunks > 0 ? ragIndexDir : undefined,
  });
  if (clone.jobId) {
    updateJob(clone.jobId, {
      knowledgeSources: stats.sources,
      knowledgeCount: stats.totalChunks,
      knowledgeFile,
      ragIndexDir: stats.totalChunks > 0 ? ragIndexDir : undefined,
    });
  }

  const updatedClone = getClone(cloneId);
  return NextResponse.json({
    success: true,
    knowledgeSources: stats.sources,
    knowledgeCount: stats.totalChunks,
    clone: updatedClone,
  });
}
