import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { randomUUID } from "crypto";

export const runtime = "nodejs";

const DATASETS_DIR = path.resolve(process.cwd(), "uploads", "datasets");

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const file = formData.get("file");

    if (!file || !(file instanceof Blob)) {
      return NextResponse.json({ error: "File is required" }, { status: 400 });
    }

    const datasetId = (formData.get("datasetId") as string) || randomUUID();
    console.log(`[API] Uploading file to dataset: ${datasetId}`);
    const targetDir = path.join(DATASETS_DIR, datasetId);
    await fs.mkdir(targetDir, { recursive: true });

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const uploadedName = (file as any).name as string | undefined;
    const filename =
      (formData.get("filename") as string) ||
      uploadedName ||
      "uploaded_file";
    const targetPath = path.join(targetDir, filename);
    await fs.writeFile(targetPath, buffer);

    // Get all files in the directory to return updated list
    let fileStats: { name: string; size: number }[] = [];
    try {
      const files = await fs.readdir(targetDir);
      fileStats = await Promise.all(
        files.map(async (f) => {
          try {
            const stat = await fs.stat(path.join(targetDir, f));
            return { name: f, size: stat.size };
          } catch (e) {
            console.error(`Failed to stat file ${f}:`, e);
            return null;
          }
        })
      ).then((results) => results.filter((r): r is { name: string; size: number } => r !== null));
    } catch (readErr) {
      console.error("Failed to read dataset directory:", readErr);
      // Fallback: return at least the current file
      fileStats = [{ name: filename, size: buffer.length }];
    }

    return NextResponse.json({
      datasetId,
      files: fileStats,
      path: targetDir,
    });
  } catch (err) {
    console.error("Dataset upload error:", err);
    return NextResponse.json({ error: "Failed to upload dataset" }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const datasetId = searchParams.get("datasetId");
    const filename = searchParams.get("filename");

    if (!datasetId || !filename) {
      return NextResponse.json({ error: "Missing datasetId or filename" }, { status: 400 });
    }

    const targetDir = path.join(DATASETS_DIR, datasetId);
    const targetPath = path.join(targetDir, filename);

    await fs.unlink(targetPath);

    // Return updated list
    const files = await fs.readdir(targetDir);
    const fileStats = await Promise.all(
      files.map(async (f) => {
        const stat = await fs.stat(path.join(targetDir, f));
        return { name: f, size: stat.size };
      })
    );

    return NextResponse.json({
      datasetId,
      files: fileStats,
    });
  } catch (err) {
    console.error("Delete error:", err);
    return NextResponse.json({ error: "Failed to delete file" }, { status: 500 });
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const datasetId = searchParams.get("datasetId");

    if (!datasetId) {
      return NextResponse.json({ error: "Missing datasetId" }, { status: 400 });
    }

    const targetDir = path.join(DATASETS_DIR, datasetId);

    try {
      await fs.access(targetDir);
    } catch {
      return NextResponse.json({ files: [] });
    }

    const files = await fs.readdir(targetDir);
    const fileStats = await Promise.all(
      files.map(async (f) => {
        try {
          const stat = await fs.stat(path.join(targetDir, f));
          return { name: f, size: stat.size };
        } catch {
          return null;
        }
      })
    ).then((results) => results.filter((r): r is { name: string; size: number } => r !== null));

    return NextResponse.json({ files: fileStats });
  } catch (err) {
    console.error("List files error:", err);
    return NextResponse.json({ error: "Failed to list files" }, { status: 500 });
  }
}
