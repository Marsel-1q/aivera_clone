"use client";

import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Play, Send, Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface CloneItem {
    id: string;
    name: string;
    status: string;
}

interface ChatMessage {
    role: "user" | "assistant";
    content: string;
}

export default function TestsPage() {
    const [clones, setClones] = useState<CloneItem[]>([]);
    const [selectedClone, setSelectedClone] = useState<string>("");
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const endRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const loadClones = async () => {
            try {
                const res = await fetch("/api/clones");
                const data = await res.json();
                setClones(data.clones || []);
            } catch (e) {
                console.error("Failed to load clones", e);
            }
        };
        loadClones();
    }, []);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSend = async () => {
        if (!selectedClone || !input.trim() || isSending) return;
        const text = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: text }]);
        setIsSending(true);
        try {
            const res = await fetch("/api/tests/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ cloneId: selectedClone, message: text }),
            });
            const data = await res.json();
            setMessages((prev) => [...prev, { role: "assistant", content: data.answer || "No answer" }]);
        } catch (e) {
            console.error(e);
            setMessages((prev) => [...prev, { role: "assistant", content: "Error while contacting clone." }]);
        } finally {
            setIsSending(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">Tests & Evaluations</h1>
                <div className="flex gap-2 items-center">
                    <Select value={selectedClone} onValueChange={setSelectedClone}>
                        <SelectTrigger className="w-64">
                            <SelectValue placeholder="Select clone" />
                        </SelectTrigger>
                        <SelectContent>
                            {clones.map((c) => (
                                <SelectItem key={c.id} value={c.id}>
                                    {c.name} ({c.status})
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button disabled={!selectedClone} className="bg-primary text-primary-foreground hover:bg-primary/90">
                        <Play className="mr-2 h-4 w-4" /> Run New Test
                    </Button>
                </div>
            </div>

            <Card className="min-h-[500px] flex flex-col">
                <CardHeader>
                    <CardTitle>Chat with Clone</CardTitle>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col space-y-4">
                    <div className="flex-1 border rounded-md p-3 overflow-y-auto space-y-3 bg-muted/30">
                        {messages.map((msg, idx) => (
                            <div key={idx} className={cn("flex gap-2", msg.role === "user" ? "justify-end" : "justify-start")}>
                                {msg.role === "assistant" && (
                                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                                        <Bot className="h-4 w-4 text-primary" />
                                    </div>
                                )}
                                <div className={cn("rounded-md px-3 py-2 text-sm max-w-[70%]", msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-background border")}>
                                    <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                                </div>
                                {msg.role === "user" && (
                                    <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
                                        <User className="h-4 w-4 text-secondary-foreground" />
                                    </div>
                                )}
                            </div>
                        ))}
                        <div ref={endRef} />
                    </div>
                    <div className="flex gap-2">
                        <Input
                            placeholder="Type a message..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSend();
                                }
                            }}
                            disabled={!selectedClone || isSending}
                        />
                        <Button onClick={handleSend} disabled={!selectedClone || isSending || !input.trim()}>
                            <Send className="h-4 w-4" />
                        </Button>
                    </div>
                    {!selectedClone && <p className="text-xs text-muted-foreground">Select a clone to start testing.</p>}
                </CardContent>
            </Card>
        </div>
    );
}
