import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

export default function SettingsPage() {
    return (
        <div className="space-y-6 max-w-2xl">
            <h1 className="text-3xl font-bold tracking-tight">Settings</h1>

            <div className="space-y-4">
                <h3 className="text-lg font-medium">Profile</h3>
                <div className="grid gap-4">
                    <div className="grid gap-2">
                        <Label htmlFor="name">Display Name</Label>
                        <Input id="name" defaultValue="John Doe" />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="email">Email</Label>
                        <Input id="email" defaultValue="john@example.com" disabled />
                    </div>
                </div>
            </div>

            <Separator />

            <div className="space-y-4">
                <h3 className="text-lg font-medium">API Keys</h3>
                <div className="grid gap-4">
                    <div className="flex gap-2">
                        <Input value="sk_live_..." readOnly className="font-mono" />
                        <Button variant="outline">Copy</Button>
                    </div>
                    <Button>Generate New Key</Button>
                </div>
            </div>
        </div>
    );
}
