import { createClient } from "@supabase/supabase-js";
import dotenv from "dotenv";
import path from "path";

dotenv.config({ path: path.resolve(process.cwd(), ".env.local") });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error("Missing env vars!");
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function test() {
  console.log("Testing connection...");
  
  // 1. Check jobs
  const { data: jobs, error: errJobs } = await supabase.from("training_jobs").select("*");
  if (errJobs) console.error("Error fetching jobs:", errJobs);
  else console.log(`Found ${jobs?.length} jobs.`);

  // 2. Check clones
  const { data: clones, error: errClones } = await supabase.from("clones").select("*");
  if (errClones) console.error("Error fetching clones:", errClones);
  else console.log(`Found ${clones?.length} clones.`);

    if (clones?.length === 0 && jobs?.length === 0) {
        console.log("No data found. Trying to insert dummy data...");
        // get a user
        const { data: { users }, error: errUsers } = await supabase.auth.admin.listUsers();
        if (errUsers || !users || users.length === 0) {
            console.log("No users found to attach data to.");
            return;
        }
        const userId = users[0].id;
        console.log(`Using user: ${userId}`);
        
        const { data: newClone, error: errInsert } = await supabase.from("clones").insert({
            user_id: userId,
            name: "Test Clone (Manual)",
            model_id: "test",
            status: "ready",
            dataset_count: 0
        }).select().single();
        
        if (errInsert) console.log("Insert failed:", errInsert);
        else console.log("Insert success:", newClone);
    }
}

test();
