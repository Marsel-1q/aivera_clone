import { NextResponse } from "next/server";
import { getClone } from "@/lib/cloneStore";
import { getJob } from "@/lib/jobStore";
import path from "path";
import { spawn } from "child_process";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface ChatPayload {
  cloneId: string;
  message: string;
}

export async function POST(request: Request) {
  const payload = (await request.json()) as ChatPayload;
  if (!payload.cloneId || !payload.message) {
    return NextResponse.json({ error: "cloneId and message are required" }, { status: 400 });
  }
  const clone = getClone(payload.cloneId);
  if (!clone) {
    console.log(`[chat] Clone not found: ${payload.cloneId}`);
    return NextResponse.json({ error: "Clone not found" }, { status: 404 });
  }
  const job = getJob(clone.jobId);
  const ragIndexDir = clone.ragIndexDir || job?.ragIndexDir;
  console.log(
    `[chat] cloneId=${payload.cloneId}, jobId=${clone.jobId}, jobStatus=${job?.status}, adapterDir=${job?.adapterDir}, ragIndexDir=${ragIndexDir}`
  );
  if (!job || job.status !== "succeeded" || !job.adapterDir) {
    console.log(`[chat] Clone not ready: job=${!!job}, status=${job?.status}, adapter=${job?.adapterDir}`);
    return NextResponse.json({ error: "Clone is not ready or adapter missing" }, { status: 400 });
  }

  try {
    const scriptPath = path.resolve(process.cwd(), "scripts", "chat_with_lora.py");
    const baseEnv = {
      ...process.env,
      PYTHONPATH: [path.resolve(process.cwd(), ".."), process.env.PYTHONPATH || ""].filter(Boolean).join(":"),
    };
    const args = [
      scriptPath,
      "--model-id",
      job.modelId,
      "--adapter-dir",
      path.resolve(job.adapterDir),
      "--message",
      payload.message,
      "--system-prompt",
      job.systemPrompt || "",
    ];

    if (ragIndexDir) {
      args.push("--rag-index-dir", path.resolve(ragIndexDir));
    }

    const proc = spawn("python3", args, { env: baseEnv });

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d.toString()));
    proc.stderr.on("data", (d) => (stderr += d.toString()));

    const code: number = await new Promise((resolve) => {
      proc.on("close", (c) => resolve(c ?? 1));
    });

    if (code !== 0) {
      console.error("Chat inference error:", stderr || stdout);
      return NextResponse.json({ error: "Inference failed", details: stderr || stdout }, { status: 500 });
    }

    const answer = stdout.trim() || "No answer";
    return NextResponse.json({ answer });
  } catch (e: any) {
    console.error("Chat inference error:", e);
    return NextResponse.json({ error: "Inference failed", details: String(e) }, { status: 500 });
  }
}
