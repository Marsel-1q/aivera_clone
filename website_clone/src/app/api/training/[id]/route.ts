import { NextResponse } from "next/server";
import { getJob } from "@/lib/repositories/jobRepository";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> }
) {
  const { id } = await ctx.params;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json(job);
}
