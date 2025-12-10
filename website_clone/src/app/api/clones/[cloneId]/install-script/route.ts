import { NextResponse } from "next/server";
import { getClone } from "@/lib/cloneStore";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
    request: Request,
    { params }: { params: Promise<{ cloneId: string }> }
) {
    const { cloneId } = await params;
    const clone = getClone(cloneId);

    if (!clone) {
        return NextResponse.json({ error: "Clone not found" }, { status: 404 });
    }

    // In a real app, this URL would point to the actual platform
    const installCommand = `bash <(curl -s https://platform.com/install_clone.sh) \\
          --clone-id ${clone.id} \\
          --token ${clone.apiKey}`;

    return NextResponse.json({ installCommand });
}
