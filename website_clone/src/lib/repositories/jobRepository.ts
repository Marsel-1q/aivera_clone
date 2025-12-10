import { createClient } from "@/lib/supabase/server";
import { TrainingJob } from "@/lib/jobStore";

interface SupabaseJob {
    id: string;
    user_id: string;
    model_id: string;
    dataset_path: string;
    system_prompt: string;
    persona: string | null;
    clone_id: string | null;
    clone_name: string | null;
    adapter_dir: string | null;
    processed_dir: string | null;
    knowledge_file: string | null;
    rag_index_dir: string | null;
    knowledge_count: number;
    knowledge_sources: any;
    status: "queued" | "running" | "succeeded" | "failed";
    logs: string[];
    error: string | null;
    created_at: number;
    updated_at: number;
}

function mapToJobRecord(row: SupabaseJob): TrainingJob {
    return {
        id: row.id,
        modelId: row.model_id,
        datasetPath: row.dataset_path,
        systemPrompt: row.system_prompt,
        persona: row.persona || undefined,
        cloneId: row.clone_id || undefined,
        cloneName: row.clone_name || undefined,
        adapterDir: row.adapter_dir || undefined,
        processedDir: row.processed_dir || undefined,
        knowledgeFile: row.knowledge_file || undefined,
        ragIndexDir: row.rag_index_dir || undefined,
        knowledgeCount: row.knowledge_count,
        knowledgeSources: row.knowledge_sources,
        status: row.status,
        logs: row.logs || [],
        error: row.error || undefined,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
    };
}

export async function getJob(id: string): Promise<TrainingJob | null> {
    const supabase = await createClient();
    const { data, error } = await supabase
        .from("training_jobs")
        .select("*")
        .eq("id", id)
        .single();

    if (error || !data) return null;
    return mapToJobRecord(data as SupabaseJob);
}

export async function listJobs(): Promise<TrainingJob[]> {
    const supabase = await createClient();
    const { data, error } = await supabase
        .from("training_jobs")
        .select("*")
        .order("created_at", { ascending: false });

    if (error || !data) {
        console.error("Error listing jobs:", error);
        return [];
    }
    return (data as SupabaseJob[]).map(mapToJobRecord);
}

export async function createJobRepo(params: {
    modelId: string;
    datasetPath: string;
    systemPrompt: string;
    persona?: string;
    cloneId?: string;
    cloneName?: string;
    adapterDir?: string;
}): Promise<TrainingJob | null> {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) throw new Error("Unauthorized");

    const now = Date.now();
    const newJob = {
        user_id: user.id,
        model_id: params.modelId,
        dataset_path: params.datasetPath,
        system_prompt: params.systemPrompt,
        persona: params.persona || null,
        clone_id: params.cloneId || null,
        clone_name: params.cloneName || null,
        adapter_dir: params.adapterDir || null,
        status: "queued",
        logs: [],
        created_at: now,
        updated_at: now,
    };

    const { data, error } = await supabase
        .from("training_jobs")
        .insert(newJob)
        .select()
        .single();

    if (error) {
        console.error("Error creating job:", error);
        return null;
    }
    return mapToJobRecord(data as SupabaseJob);
}

export async function updateJobRepo(id: string, updates: Partial<TrainingJob>) {
    const supabase = await createClient();

    const mappedUpdates: any = {
        updated_at: Date.now()
    };

    if (updates.status) mappedUpdates.status = updates.status;
    if (updates.logs) mappedUpdates.logs = updates.logs;
    if (updates.error) mappedUpdates.error = updates.error;
    if (updates.adapterDir) mappedUpdates.adapter_dir = updates.adapterDir;
    if (updates.processedDir) mappedUpdates.processed_dir = updates.processedDir;
    if (updates.knowledgeFile) mappedUpdates.knowledge_file = updates.knowledgeFile;
    if (updates.ragIndexDir) mappedUpdates.rag_index_dir = updates.ragIndexDir;
    if (updates.knowledgeCount !== undefined) mappedUpdates.knowledge_count = updates.knowledgeCount;
    if (updates.knowledgeSources) mappedUpdates.knowledge_sources = updates.knowledgeSources;

    const { data, error } = await supabase
        .from("training_jobs")
        .update(mappedUpdates)
        .eq("id", id)
        .select()
        .single();

    if (error) {
        console.error("Error updating job:", error);
        return null;
    }
    return mapToJobRecord(data as SupabaseJob);
}


export async function appendLogRepo(id: string, line: string) {
    const supabase = await createClient();
    // note: arrays in supabase postgres updates can be tricky, 
    // doing a read-modify-write is safer for now without stored procedures
    // OR we can use postgres array_append. 
    // BUT we need to be careful about RLS. 

    // For simplicity efficiently (and since logs might be frequent), 
    // let's try a direct RPC or just an update if concurrency isn't huge.
    // Given the constraints, let's just fetch-update for now.

    const { data: job } = await supabase.from('training_jobs').select('logs').eq('id', id).single();
    if (!job) return;

    const newLogs = [...(job.logs || []), line];

    await supabase
        .from('training_jobs')
        .update({
            logs: newLogs,
            updated_at: Date.now()
        })
        .eq('id', id);
}
