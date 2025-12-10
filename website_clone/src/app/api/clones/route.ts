import { NextResponse } from "next/server";
import { listClones } from "@/lib/repositories/cloneRepository";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const clones = await listClones();
  return NextResponse.json(clones);
}
