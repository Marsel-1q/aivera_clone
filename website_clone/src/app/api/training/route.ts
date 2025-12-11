import { NextResponse } from "next/server";
import path from "path";
import { spawn } from "child_process";
import { promises as fs } from "fs";
import { z } from "zod";
import { createJobRepo, updateJobRepo, appendLogRepo, getJob } from "@/lib/repositories/jobRepository";
import { createCloneRepo, updateCloneRepo } from "@/lib/repositories/cloneRepository";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const DATASETS_DIR = path.resolve(process.cwd(), "uploads", "datasets");
const OUTPUTS_DIR = path.resolve(process.cwd(), "uploads", "jobs");

// Zod validation schema for training payload
const TrainPayloadSchema = z.object({
  modelId: z.string()
    .min(1, "modelId is required")
    .max(200, "modelId too long")
    .regex(/^[a-zA-Z0-9\-_\/\.]+$/, "modelId contains invalid characters"),
  datasetId: z.string()
    .uuid("datasetId must be a valid UUID"),
  systemPrompt: z.string()
    .max(10000, "systemPrompt too long")
    .optional()
    .default(""),
  persona: z.string()
    .max(100, "persona too long")
    .optional(),
  cloneName: z.string()
    .max(100, "cloneName too long")
    .optional(),
});

type TrainPayload = z.infer<typeof TrainPayloadSchema>;

export async function POST(request: Request) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let payload: TrainPayload;
  try {
    const body = await request.json();
    payload = TrainPayloadSchema.parse(body);
  } catch (err) {
    if (err instanceof z.ZodError) {
      const issues = err.issues || [];
      return NextResponse.json({
        error: "Validation failed",
        details: issues.map((e: z.ZodIssue) => ({ path: e.path.join('.'), message: e.message }))
      }, { status: 400 });
    }
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const datasetPath = path.join(DATASETS_DIR, payload.datasetId);
  const datasetExists = await fs.stat(datasetPath).then(() => true).catch(() => false);
  if (!datasetExists) {
    return NextResponse.json({ error: "Dataset not found" }, { status: 400 });
  }
  const datasetFiles = await fs.readdir(datasetPath).catch(() => []);
  await fs.mkdir(OUTPUTS_DIR, { recursive: true });

  // Create Job in Supabase
  const job = await createJobRepo({
    modelId: payload.modelId,
    datasetPath,
    systemPrompt: payload.systemPrompt || "",
    persona: payload.persona,
    adapterDir: path.join(OUTPUTS_DIR, "pending"),
  });

  if (!job) {
    return NextResponse.json({ error: "Failed to create job" }, { status: 500 });
  }

  // Create Clone in Supabase
  const clone = await createCloneRepo({
    name: payload.cloneName?.trim() || "New Clone",
    modelId: payload.modelId,
    jobId: job.id,
    status: "training",
    datasetCount: datasetFiles.length,
    startedAt: job.createdAt,
  });

  if (!clone) {
    return NextResponse.json({ error: "Failed to create clone" }, { status: 500 });
  }

  // Link job to clone
  await updateJobRepo(job.id, {
    cloneId: clone.id,
    cloneName: clone.name
  });

  job.cloneId = clone.id;
  job.cloneName = clone.name;

  // For demo: simulate training unless explicitly enabled
  const enableRealTrain = process.env.ENABLE_REAL_TRAINING === "true";
  if (!enableRealTrain) {
    simulateJob(job.id); // fire and forget
    return NextResponse.json({ jobId: job.id, cloneId: clone.id, status: "queued", simulated: true });
  }

  runPipeline(job.id, payload); // fire and forget
  return NextResponse.json({ jobId: job.id, cloneId: clone.id, status: "queued", simulated: false });
}

async function simulateJob(jobId: string) {
  await updateJobRepo(jobId, { status: "running" });
  await appendLogRepo(jobId, "Simulated training started.");
  setTimeout(async () => {
    await appendLogRepo(jobId, "Simulated training finished.");
    await updateJobRepo(jobId, { status: "succeeded" });
    // update clone status if linked
    const job = await getJob(jobId);
    if (job?.cloneId) {
      await updateCloneRepo(job.cloneId, { status: "ready" });
    }
  }, 5000);
}

async function readKnowledgeStats(jobId: string, knowledgeFile: string) {
  try {
    const content = await fs.readFile(knowledgeFile, "utf-8");
    const lines = content.split("\n").filter(Boolean);
    const counters: Record<string, { chunks: number; size?: number; displayName: string; source: string }> = {};
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
          counters[source] = { chunks: 0, size, displayName, source };
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
    await appendLogRepo(jobId, `Failed to read knowledge file ${knowledgeFile}: ${String(err)}`);
    return { totalChunks: 0, sources: [] as { source: string; chunks: number; displayName?: string; size?: number }[] };
  }
}

function runLoggedProcess(
  jobId: string,
  label: string,
  command: string,
  args: string[],
  opts: Parameters<typeof spawn>[2]
): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, opts);
    proc.stdout.on("data", (data) => appendLogRepo(jobId, data.toString()));
    proc.stderr.on("data", (data) => appendLogRepo(jobId, data.toString()));
    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`${label} exited with code ${code}`));
      } else {
        resolve();
      }
    });
  });
}

async function runRagIndex(jobId: string, knowledgeFile: string, ragIndexDir: string, env: NodeJS.ProcessEnv) {
  const args = [
    "-m",
    "rag.index_builder",
    "--knowledge-file",
    knowledgeFile,
    "--output-dir",
    ragIndexDir,
  ];
  await appendLogRepo(jobId, `Building RAG index from ${knowledgeFile}`);
  await runLoggedProcess(jobId, "rag_index", "python3", args.filter(Boolean), { cwd: REPO_ROOT, env });
  await appendLogRepo(jobId, `RAG index saved to ${ragIndexDir}`);
}

async function runPipeline(jobId: string, payload: TrainPayload) {
  const jobOutput = path.join(OUTPUTS_DIR, jobId);
  const cliPath = path.join(REPO_ROOT, "dataset_pipeline", "cli.py");
  const trainPath = path.join(REPO_ROOT, "train_qlora.py");
  const processedDir = path.join(jobOutput, "processed_dataset");
  const trainFile = path.join(processedDir, "train.jsonl");
  const evalFile = path.join(processedDir, "eval.jsonl");
  const knowledgeFile = path.join(processedDir, "knowledge.jsonl");
  const ragIndexDir = path.join(jobOutput, "rag_index");
  const persona = payload.persona?.trim() || "user_persona";
  const outputDir = path.join(jobOutput, "outputs");
  const adapterDir = path.join(outputDir, "lora_adapter");

  await updateJobRepo(jobId, { status: "running", adapterDir, processedDir, knowledgeFile, ragIndexDir });
  fs.mkdir(processedDir, { recursive: true }).catch(() => { });
  fs.mkdir(outputDir, { recursive: true }).catch(() => { });

  const baseEnv = {
    ...process.env,
    PYTHONPATH: [REPO_ROOT, process.env.PYTHONPATH || ""].filter(Boolean).join(":"),
  };

  try {
    const cliArgs = [
      cliPath,
      "--inputs",
      payload.datasetId ? path.join(DATASETS_DIR, payload.datasetId) : "",
      "--output-dir",
      processedDir,
      "--persona",
      persona,
      "--format",
      "huggingface",
      "--eval-split",
      "0.1",
    ];

    await runLoggedProcess(jobId, "dataset_pipeline", "python3", cliArgs.filter(Boolean), { cwd: REPO_ROOT, env: baseEnv });

    const knowledgeStats = await readKnowledgeStats(jobId, knowledgeFile);
    await updateJobRepo(jobId, {
      knowledgeCount: knowledgeStats.totalChunks,
      knowledgeSources: knowledgeStats.sources,
    });
    const job = await getJob(jobId);
    if (job?.cloneId) {
      await updateCloneRepo(job.cloneId, {
        knowledgeCount: knowledgeStats.totalChunks,
        knowledgeSources: knowledgeStats.sources,
        knowledgeFile,
        ragIndexDir,
      });
    }

    if (knowledgeStats.totalChunks > 0) {
      try {
        await runRagIndex(jobId, knowledgeFile, ragIndexDir, baseEnv);
      } catch (ragErr: any) {
        await appendLogRepo(jobId, `RAG index build failed (will continue without RAG): ${ragErr?.message || ragErr}`);
      }
    } else {
      await appendLogRepo(jobId, "No knowledge chunks found, skipping RAG index build.");
    }

    const trainArgs = [
      trainPath,
      "--train-file",
      trainFile,
      "--eval-file",
      evalFile,
      "--model-id",
      payload.modelId,
      "--system-prompt",
      payload.systemPrompt || "",
      "--output-dir",
      outputDir,
      "--adapter-dir",
      adapterDir,
    ];

    await runLoggedProcess(jobId, "train_qlora", "python3", trainArgs.filter(Boolean), { cwd: REPO_ROOT, env: baseEnv });

    await updateJobRepo(jobId, { status: "succeeded" });
    const okJob = await getJob(jobId);
    if (okJob?.cloneId) await updateCloneRepo(okJob.cloneId, { status: "ready" });
  } catch (err: any) {
    await updateJobRepo(jobId, { status: "failed", error: err?.message || String(err) });
    const failedJob = await getJob(jobId);
    if (failedJob?.cloneId) await updateCloneRepo(failedJob.cloneId, { status: "failed" });
  }
}
