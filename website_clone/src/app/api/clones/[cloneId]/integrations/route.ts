import { NextResponse } from "next/server";
import { getIntegrations } from "@/lib/integrationStore";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ cloneId: string }> }
) {
  const { cloneId } = await params;
  const integrations = await getIntegrations(cloneId);
  return NextResponse.json({ integrations });
}
