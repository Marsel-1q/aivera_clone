import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MessageCircle, Globe, Server } from "lucide-react";

export default function DeployPage() {
    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Deploy & Integrations</h1>

            <div className="grid gap-6 md:grid-cols-3">
                <Card className="bg-card border-border/50">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Telegram</CardTitle>
                        <MessageCircle className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">Not Connected</div>
                        <Button variant="outline" className="w-full mt-4">Connect Bot</Button>
                    </CardContent>
                </Card>
                <Card className="bg-card border-border/50">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Web Widget</CardTitle>
                        <Globe className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">Ready</div>
                        <Button variant="outline" className="w-full mt-4">Get Code</Button>
                    </CardContent>
                </Card>
                <Card className="bg-card border-border/50">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Local Node</CardTitle>
                        <Server className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">0 Active</div>
                        <Button variant="outline" className="w-full mt-4">Download Node</Button>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
