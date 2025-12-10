import { Button } from "@/components/ui/button";
import { FolderPlus } from "lucide-react";

export default function ProjectsPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
                <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
                    <FolderPlus className="mr-2 h-4 w-4" /> New Project
                </Button>
            </div>

            <div className="flex flex-col items-center justify-center h-[400px] border border-dashed border-border rounded-lg bg-card/50">
                <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mb-4">
                    <FolderPlus className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-medium">No projects yet</h3>
                <p className="text-muted-foreground mt-2 mb-6">Group your clones and datasets into projects.</p>
                <Button variant="outline">Create your first Project</Button>
            </div>
        </div>
    );
}
