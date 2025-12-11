import { createClient } from "@/lib/supabase/server";
import { CloneRecord } from "@/lib/cloneStore";

// Type definition matching Supabase table structure (snake_case)
interface SupabaseClone {
    id: string;
    user_id: string;
    name: string;
    model_id: string;
    job_id: string | null;
    status: "training" | "ready" | "failed";
    dataset_count: number;
    dataset_id: string | null;
    messengers: string[] | null;
    api_key: string | null;
    is_running: boolean;
    started_at: number | null;
    created_at: number;
    updated_at: number;
    knowledge_count: number;
    knowledge_sources: any; // jsonb
    knowledge_file: string | null;
    rag_index_dir: string | null;
}

function mapToCloneRecord(row: SupabaseClone): CloneRecord {
    return {
        id: row.id,
        userId: row.user_id,
        name: row.name,
        modelId: row.model_id,
        jobId: row.job_id || "",
        status: row.status,
        datasetCount: row.dataset_count,
        datasetId: row.dataset_id || undefined,
        messengers: row.messengers || [],
        apiKey: row.api_key || undefined,
        isRunning: row.is_running,
        startedAt: row.started_at || undefined,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        knowledgeCount: row.knowledge_count,
        knowledgeSources: row.knowledge_sources, // assuming compatible structure
        knowledgeFile: row.knowledge_file || undefined,
        ragIndexDir: row.rag_index_dir || undefined,
    };
}

export async function getClone(id: string): Promise<CloneRecord | null> {
    const supabase = await createClient();
    const { data, error } = await supabase
        .from("clones")
        .select("*")
        .eq("id", id)
        .single();

    if (error || !data) return null;
    return mapToCloneRecord(data as SupabaseClone);
}

export async function listClones(): Promise<CloneRecord[]> {
    const supabase = await createClient();
    const { data, error } = await supabase
        .from("clones")
        .select("*")
        .order("created_at", { ascending: false });

    if (error || !data) {
        console.error("Error listing clones:", error);
        return [];
    }
    return (data as SupabaseClone[]).map(mapToCloneRecord);
}

export async function createCloneRepo(params: {
    name: string;
    modelId: string;
    jobId: string;
    status?: "training" | "ready" | "failed";
    datasetCount?: number;
    datasetId?: string;
    startedAt?: number;
}): Promise<CloneRecord | null> {
    const supabase = await createClient();

    // Get current user to ensure we are authenticated
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) throw new Error("Unauthorized");

    const now = Date.now();
    const newClone = {
        user_id: user.id,
        name: params.name,
        model_id: params.modelId,
        job_id: params.jobId,
        status: params.status || "training",
        dataset_count: params.datasetCount || 0,
        dataset_id: params.datasetId || null,
        is_running: false,
        started_at: params.startedAt || now,
        created_at: now,
        updated_at: now,
        // generate a simple API key for now (in a real app, use a secure generator)
        api_key: crypto.randomUUID().replace(/-/g, ""),
    };

    const { data, error } = await supabase
        .from("clones")
        .insert(newClone)
        .select()
        .single();

    if (error) {
        console.error("Error creating clone:", error);
        return null;
    }
    return mapToCloneRecord(data as SupabaseClone);
}

export async function updateCloneRepo(id: string, updates: Partial<CloneRecord>) {
    const supabase = await createClient();

    const mappedUpdates: any = {
        updated_at: Date.now()
    };

    if (updates.status) mappedUpdates.status = updates.status;
    if (updates.name) mappedUpdates.name = updates.name;
    if (updates.isRunning !== undefined) mappedUpdates.is_running = updates.isRunning;
    if (updates.messengers) mappedUpdates.messengers = updates.messengers;
    if (updates.datasetCount !== undefined) mappedUpdates.dataset_count = updates.datasetCount;
    if (updates.datasetId) mappedUpdates.dataset_id = updates.datasetId;
    if (updates.knowledgeCount !== undefined) mappedUpdates.knowledge_count = updates.knowledgeCount;
    if (updates.knowledgeSources) mappedUpdates.knowledge_sources = updates.knowledgeSources;
    if (updates.knowledgeFile) mappedUpdates.knowledge_file = updates.knowledgeFile;
    if (updates.ragIndexDir) mappedUpdates.rag_index_dir = updates.ragIndexDir;

    const { data, error } = await supabase
        .from("clones")
        .update(mappedUpdates)
        .eq("id", id)
        .select()
        .single();

    if (error) {
        console.error("Error updating clone:", error);
        return null;
    }
    return mapToCloneRecord(data as SupabaseClone);
}
