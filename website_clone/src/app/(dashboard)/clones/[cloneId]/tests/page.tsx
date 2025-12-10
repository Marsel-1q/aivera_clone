"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Send, RefreshCw, ThumbsUp, ThumbsDown, Bot } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { CloneRecord } from "@/lib/cloneStore";

interface ChatMessage {
    role: "user" | "assistant";
    content: string;
}

export default function CloneTestsPage() {
    const params = useParams();
    const cloneId = params.cloneId as string;
    const [clone, setClone] = useState<CloneRecord | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const endRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const loadClone = async () => {
            try {
                const res = await fetch(`/api/clones/${cloneId}`);
                if (res.ok) {
                    const data = await res.json();
                    setClone(data);
                    setMessages([{ role: "assistant", content: `Hi, I'm ${data.name || "your clone"}. Ask me anything.` }]);
                }
            } catch (e) {
                console.error("Failed to load clone", e);
            }
        };
        loadClone();
    }, [cloneId]);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isSending || !cloneId) return;
        const text = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: text }]);
        setIsSending(true);
        setError(null);
        try {
            const res = await fetch("/api/tests/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ cloneId, message: text }),
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                setError(data.error || "Inference failed");
                setMessages((prev) => [...prev, { role: "assistant", content: "Clone is not ready right now." }]);
            } else {
                setMessages((prev) => [...prev, { role: "assistant", content: data.answer || "No answer" }]);
            }
        } catch (e) {
            console.error(e);
            setError("Failed to contact clone");
            setMessages((prev) => [...prev, { role: "assistant", content: "Error while contacting clone." }]);
        } finally {
            setIsSending(false);
        }
    };

    return (
        <div className="flex h-[calc(100vh-200px)] flex-col space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-medium">Test Playground</h2>
                    <p className="text-sm text-muted-foreground">
                        Interact with your clone to verify its behavior and knowledge.
                    </p>
                    {clone?.status !== "ready" && (
                        <p className="text-xs text-amber-400 mt-1 flex items-center gap-1">
                            <Bot className="h-3 w-3" /> {clone?.status === "training" ? "Training in progress" : "Clone not ready"}
                        </p>
                    )}
                </div>
                <Button variant="outline" size="sm" onClick={() => setMessages(clone ? [{ role: "assistant", content: `Hi, I'm ${clone.name}. Ask me anything.` }] : [])}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Reset Chat
                </Button>
            </div>

            <Card className="flex-1 flex flex-col overflow-hidden bg-card/50 backdrop-blur-sm border-primary/20">
                <ScrollArea className="flex-1 p-4">
                    <div className="space-y-4">
                        {messages.map((message, index) => (
                            <div
                                key={index}
                                className={`flex items-start gap-3 ${message.role === "user" ? "flex-row-reverse" : ""
                                    }`}
                            >
                                <Avatar className="h-8 w-8">
                                    <AvatarImage src={message.role === "user" ? "/user-avatar.png" : "/bot-avatar.png"} />
                                    <AvatarFallback>{message.role === "user" ? "U" : "AI"}</AvatarFallback>
                                </Avatar>
                                <div
                                    className={`rounded-lg px-4 py-2 max-w-[80%] text-sm ${message.role === "user"
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-muted"
                                        }`}
                                >
                                    {message.content}
                                </div>
                                {message.role === "assistant" && (
                                    <div className="flex flex-col gap-1 mt-1">
                                        <Button variant="ghost" size="icon" className="h-6 w-6">
                                            <ThumbsUp className="h-3 w-3" />
                                        </Button>
                                        <Button variant="ghost" size="icon" className="h-6 w-6">
                                            <ThumbsDown className="h-3 w-3" />
                                        </Button>
                                    </div>
                                )}
                            </div>
                        ))}
                        <div ref={endRef} />
                    </div>
                </ScrollArea>
                <div className="p-4 border-t border-border bg-background/50">
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            handleSend();
                        }}
                        className="flex gap-2"
                    >
                        <Input
                            placeholder="Type a message..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            className="flex-1"
                            disabled={isSending}
                        />
                        <Button type="submit" size="icon" disabled={!input.trim() || isSending}>
                            <Send className="h-4 w-4" />
                        </Button>
                    </form>
                    {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
                </div>
            </Card>
        </div>
    );
}
