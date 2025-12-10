import { createClient } from "@supabase/supabase-js";
import dotenv from "dotenv";
import path from "path";
import readline from "readline";

dotenv.config({ path: path.resolve(process.cwd(), ".env.local") });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
    console.error("Missing env vars!");
    process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function main() {
    console.log("=== Checking Clone Ownership ===");

    // 1. Fetch all users
    const { data: { users }, error: errUsers } = await supabase.auth.admin.listUsers();
    if (errUsers || !users) {
        console.error("Error listing users:", errUsers);
        return;
    }
    console.log(`\nFound ${users.length} users:`);
    users.forEach(u => console.log(` - ID: ${u.id} | Email: ${u.email} | Created: ${u.created_at}`));

    // 2. Fetch all clones
    const { data: clones, error: errClones } = await supabase.from("clones").select("*");
    if (errClones) {
        console.error("Error listing clones:", errClones);
        return;
    }
    console.log(`\nFound ${clones?.length} clones:`);
    const orphans: any[] = [];

    clones?.forEach(c => {
        const owner = users.find(u => u.id === c.user_id);
        const ownerInfo = owner ? `Email: ${owner.email}` : "!!! ORPHAN (Owner not found in users list) !!!";
        console.log(` - Clone: ${c.id} (${c.name}) | OwnerID: ${c.user_id} | ${ownerInfo}`);

        if (!owner) orphans.push(c);
    });

    // 2. Fetch all clones (using previous variable)
    if (clones) {
        console.log(`\nFound ${clones?.length} clones:`);
        clones?.forEach(c => console.log(` - Clone: ${c.id} (Name: ${c.name}) (Job: ${c.job_id})`));
    }

    const { data: jobs, error: errJobs } = await supabase.from("training_jobs").select("*");
    if (errJobs) {
        console.error("Error listing jobs:", errJobs);
    } else {
        console.log(`\nFound ${jobs?.length} jobs:`);
        jobs?.forEach(j => console.log(` - Job: ${j.id} (Status: ${j.status}) (Clone: ${j.clone_id})`));
    }

    if (users.length === 0) {
        console.log("\nNo users found to assign clones to.");
        return;
    }

    // 3. Auto-fix logic (interactive)
    // If there is only 1 user, and there are clones (orphan or not) that are NOT owned by this user (or we just want to force align), offer it.

    // Sort users by creation date descending (newest first)
    const newestUser = users.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];

    console.log(`\nActive User (Newest): ${newestUser.email} (${newestUser.id})`);

    // Find clones that define a DIFFERENT user_id or don't exist
    const clonesToFix = clones?.filter(c => c.user_id !== newestUser.id) || [];

    if (clonesToFix.length > 0) {
        console.log(`\nFound ${clonesToFix.length} clones that do NOT belong to the newest user.`);

        const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

        rl.question(`\nDo you want to reassig ALL ${clones?.length} clones to ${newestUser.email}? (y/n): `, async (answer) => {
            if (answer.toLowerCase() === 'y') {
                console.log("Reassigning...");

                // Update clones
                const { error: updateErr } = await supabase
                    .from("clones")
                    .update({ user_id: newestUser.id })
                    .neq("user_id", newestUser.id); // Update all that are different

                if (updateErr) console.error("Update Clones Failed:", updateErr);
                else console.log("Clones updated successfully.");

                // Update jobs (important for consistency!)
                const { error: updateJobErr } = await supabase
                    .from("training_jobs")
                    .update({ user_id: newestUser.id })
                    .neq("user_id", newestUser.id);

                if (updateJobErr) console.error("Update Jobs Failed:", updateJobErr);
                else console.log("Jobs updated successfully.");

            } else {
                console.log("Skipping update.");
            }
            rl.close();
            process.exit(0);
        });
    } else {
        console.log("\nAll clones already belong to the newest user. No fix needed.");
        process.exit(0);
    }
}

main();
