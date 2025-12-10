import { NextResponse } from "next/server";
import { upsertIntegration, getIntegrations } from "@/lib/integrationStore";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function runTelegramAction(action: "start" | "stop", token?: string): Promise<{ ok: boolean; error?: string }> {
  // Stub runner: integrate with ai-clone-bundle later.
  if (action === "start" && !token) return { ok: false, error: "Bot token is required to start" };
  try {
    // Placeholder: log command. In real setup, call ai-clone-bundle launcher.
    console.log(`[telegram] ${action} bot`, token ? `${token.slice(0, 6)}...` : "");
    return { ok: true };
  } catch (err: any) {
    return { ok: false, error: err?.message || String(err) };
  }
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ cloneId: string }> }
) {
  const { cloneId } = await params;
  const body = await request.json().catch(() => ({}));
  const token = body.token as string | undefined;
  const activate = body.active as boolean | undefined;
  const existing = await getIntegrations(cloneId);
  const currentTelegram = existing.find((i) => i.platform === "telegram");

  if (token !== undefined && typeof token !== "string") {
    return NextResponse.json({ error: "Invalid token" }, { status: 400 });
  }

  // Update token first (without activating)
  if (token) {
    await upsertIntegration(cloneId, "telegram", { token });
  }

  if (activate !== undefined) {
    const effectiveToken = token || currentTelegram?.token;
    const result = await runTelegramAction(activate ? "start" : "stop", effectiveToken);
    if (!result.ok) {
      return NextResponse.json({ error: result.error || "Failed to configure Telegram" }, { status: 400 });
    }
    await upsertIntegration(cloneId, "telegram", { active: activate });
  }

  const integrations = await upsertIntegration(cloneId, "telegram", {});
  return NextResponse.json({ integrations });
}
