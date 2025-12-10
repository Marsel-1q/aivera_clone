import { NextResponse } from "next/server";
import { getClone, updateClone } from "@/lib/cloneStore";
import { startCloneWorker, stopCloneWorker } from "@/lib/workerManager";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
    request: Request,
    { params }: { params: Promise<{ cloneId: string }> }
) {
    const { cloneId } = await params;
    const body = await request.json();
    const { action } = body; // "start" or "stop"

    const clone = getClone(cloneId);
    if (!clone) {
        return NextResponse.json({ error: "Clone not found" }, { status: 404 });
    }

    if (action === "start") {
        const res = await startCloneWorker(cloneId);
        if (!res.ok) return NextResponse.json({ error: res.error }, { status: 400 });
        return NextResponse.json({ success: true, isRunning: true });
    } else if (action === "stop") {
        const res = stopCloneWorker(cloneId);
        if (!res.ok) return NextResponse.json({ error: res.error }, { status: 400 });
        return NextResponse.json({ success: true, isRunning: false });
    }

    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
}
