import { createClient } from "@supabase/supabase-js";
import dotenv from "dotenv";
import path from "path";

dotenv.config({ path: path.resolve(process.cwd(), ".env.local") });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
    process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function fix() {
    console.log("Fixing broken job-clone links...");

    // 1. Get all clones
    const { data: clones } = await supabase.from("clones").select("*");

    if (!clones) return;

    for (const clone of clones) {
        if (clone.job_id) {
            // Find the job
            const { data: job } = await supabase.from("training_jobs").select("*").eq("id", clone.job_id).single();
            if (job && !job.clone_id) {
                console.log(`Linking Job ${job.id} to Clone ${clone.id}...`);
                await supabase.from("training_jobs").update({ clone_id: clone.id, clone_name: clone.name }).eq("id", job.id);
                console.log("Done.");
            }
        }
    }
}

fix();
