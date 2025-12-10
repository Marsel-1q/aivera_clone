import { Button } from "@/components/ui/button";
import { Upload } from "lucide-react";

export default function DatasetsPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">Datasets</h1>
                <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
                    <Upload className="mr-2 h-4 w-4" /> Upload Data
                </Button>
            </div>

            <div className="rounded-md border border-border bg-card">
                <div className="p-4 text-center text-muted-foreground">
                    No datasets uploaded yet.
                </div>
            </div>
        </div>
    );
}
