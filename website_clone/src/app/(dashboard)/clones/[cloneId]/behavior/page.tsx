"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Save } from "lucide-react";

export default function CloneBehaviorPage() {
    return (
        <div className="space-y-6 max-w-4xl">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-medium">Behavior & Personality</h2>
                    <p className="text-sm text-muted-foreground">
                        Define how your clone speaks, thinks, and behaves.
                    </p>
                </div>
                <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
                    <Save className="mr-2 h-4 w-4" />
                    Save Changes
                </Button>
            </div>

            <div className="grid gap-6">
                <Card className="bg-card/50 backdrop-blur-sm border-primary/20">
                    <CardHeader>
                        <CardTitle>Core Identity</CardTitle>
                        <CardDescription>The fundamental instructions for your clone.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="system-prompt">System Prompt</Label>
                            <Textarea
                                id="system-prompt"
                                placeholder="You are a helpful AI assistant..."
                                className="min-h-[200px] font-mono text-sm"
                                defaultValue="You are a digital clone of [User Name]. You share their knowledge, tone, and style. Your goal is to assist users by answering questions based on the provided knowledge base. Be concise, professional, and helpful."
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="greeting">Greeting Message</Label>
                            <Input
                                id="greeting"
                                placeholder="Hello! How can I help you today?"
                                defaultValue="Hi there! I'm [Clone Name]. Ask me anything about [Topic]."
                            />
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-card/50 backdrop-blur-sm border-primary/20">
                    <CardHeader>
                        <CardTitle>Model Settings</CardTitle>
                        <CardDescription>Fine-tune the model's output characteristics.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="space-y-2">
                            <Label>Language</Label>
                            <Select defaultValue="en">
                                <SelectTrigger>
                                    <SelectValue placeholder="Select language" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="en">English</SelectItem>
                                    <SelectItem value="es">Spanish</SelectItem>
                                    <SelectItem value="fr">French</SelectItem>
                                    <SelectItem value="de">German</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-4">
                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <Label>Creativity (Temperature)</Label>
                                    <span className="text-sm text-muted-foreground">0.7</span>
                                </div>
                                <Slider defaultValue={[0.7]} max={1} step={0.1} />
                                <p className="text-xs text-muted-foreground">
                                    Higher values make the output more random, while lower values make it more focused and deterministic.
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center justify-between space-x-2">
                            <div className="space-y-0.5">
                                <Label>Enable Code Interpreter</Label>
                                <p className="text-xs text-muted-foreground">
                                    Allow the clone to write and execute code.
                                </p>
                            </div>
                            <Switch />
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
