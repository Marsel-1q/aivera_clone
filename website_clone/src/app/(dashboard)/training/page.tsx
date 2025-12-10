import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function TrainingPage() {
    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Training Jobs</h1>

            <div className="grid gap-4">
                <Card className="bg-card border-border/50">
                    <CardHeader>
                        <CardTitle className="text-lg">Active Jobs</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-center py-8 text-muted-foreground">
                            No active training jobs.
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
