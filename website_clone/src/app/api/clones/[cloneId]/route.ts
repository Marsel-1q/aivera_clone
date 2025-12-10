import { NextResponse } from "next/server";
import { getClone, updateCloneRepo } from "@/lib/repositories/cloneRepository";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
    request: Request,
    { params }: { params: Promise<{ cloneId: string }> }
) {
    const { cloneId } = await params;
    const clone = await getClone(cloneId);

    if (!clone) {
        return NextResponse.json({ error: "Clone not found" }, { status: 404 });
    }

    return NextResponse.json(clone);
}

export async function PATCH(
    request: Request,
    { params }: { params: Promise<{ cloneId: string }> }
) {
    const { cloneId } = await params;
    const body = await request.json();

    const updatedClone = await updateCloneRepo(cloneId, {
        name: body.name,
        datasetId: body.datasetId,
        datasetCount: body.datasetCount,
    });

    if (!updatedClone) {
        return NextResponse.json({ error: "Clone not found" }, { status: 404 });
    }

    return NextResponse.json(updatedClone);
}
