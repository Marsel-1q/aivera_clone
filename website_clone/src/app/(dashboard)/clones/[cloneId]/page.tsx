"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { MessageSquare, Clock, ThumbsUp, Activity, Play, Square, Terminal, Copy, Check, Edit2, Save, X, Zap, Cpu, Network } from "lucide-react";
import { CloneRecord } from "@/lib/cloneStore";
import { GlassCard } from "@/components/ui/glass-card";
import { NeonButton } from "@/components/ui/neon-button";
import { motion, AnimatePresence } from "framer-motion";
import { LineChart, Line, ResponsiveContainer } from "recharts";

// Mock data for sparklines
const sparklineData = Array.from({ length: 20 }, (_, i) => ({
    value: Math.floor(Math.random() * 100) + 50 + Math.sin(i) * 20
}));

export default function CloneOverviewPage() {
    const params = useParams();
    const cloneId = params.cloneId as string;

    const [clone, setClone] = useState<CloneRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [isRunning, setIsRunning] = useState(false);
    const [installScript, setInstallScript] = useState("");
    const [isRenaming, setIsRenaming] = useState(false);
    const [newName, setNewName] = useState("");
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        fetchCloneData();
    }, [cloneId]);

    const fetchCloneData = async () => {
        try {
            const res = await fetch(`/api/clones/${cloneId}`);
            if (res.ok) {
                const data = await res.json();
                setClone(data);
                setIsRunning(data.isRunning || false);
                setNewName(data.name);
            }
        } catch (error) {
            console.error("Failed to fetch clone data", error);
        } finally {
            setLoading(false);
        }
    };

    const handleRename = async () => {
        if (!newName.trim()) return;
        try {
            const res = await fetch(`/api/clones/${cloneId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: newName }),
            });
            if (res.ok) {
                const updated = await res.json();
                setClone(updated);
                setIsRenaming(false);
            }
        } catch (error) {
            console.error("Failed to rename clone", error);
        }
    };

    const toggleCloneStatus = async () => {
        const action = isRunning ? "stop" : "start";
        try {
            const res = await fetch(`/api/clones/${cloneId}/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action }),
            });
            if (res.ok) {
                const data = await res.json();
                setIsRunning(data.isRunning);
                fetchCloneData();
            }
        } catch (error) {
            console.error(`Failed to ${action} clone`, error);
        }
    };

    const generateInstallScript = async () => {
        try {
            const res = await fetch(`/api/clones/${cloneId}/install-script`);
            if (res.ok) {
                const data = await res.json();
                setInstallScript(data.installCommand);
            }
        } catch (error) {
            console.error("Failed to generate install script", error);
        }
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(installScript);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (loading) return (
        <div className="flex items-center justify-center h-[50vh]">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
        </div>
    );

    if (!clone) return <div className="text-center text-muted-foreground p-10">Clone not found</div>;

    return (
        <div className="space-y-8 p-2">
            {/* Header Section */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col md:flex-row gap-6 justify-between items-start md:items-center relative z-10"
            >
                <div className="space-y-1">
                    <div className="flex items-center gap-3">
                        {isRenaming ? (
                            <div className="flex items-center gap-2 bg-background/50 p-1 rounded-lg border border-primary/20 backdrop-blur-md">
                                <Input
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    className="h-8 w-[250px] bg-transparent border-none focus-visible:ring-0 text-xl font-bold"
                                    autoFocus
                                />
                                <button onClick={handleRename} className="p-1 hover:text-green-400 transition-colors"><Save className="h-4 w-4" /></button>
                                <button onClick={() => setIsRenaming(false)} className="p-1 hover:text-red-400 transition-colors"><X className="h-4 w-4" /></button>
                            </div>
                        ) : (
                            <div className="flex items-center gap-3 group">
                                <h1 className="text-4xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-primary via-purple-400 to-accent animate-gradient-x">
                                    {clone.name}
                                </h1>
                                <button
                                    onClick={() => setIsRenaming(true)}
                                    className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-primary"
                                >
                                    <Edit2 className="h-5 w-5" />
                                </button>
                            </div>
                        )}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                            <Cpu className="h-3 w-3" /> {clone.modelId}
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1.5">
                            <span className={`relative flex h-2 w-2`}>
                                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isRunning ? "bg-green-400" : "bg-red-400"}`}></span>
                                <span className={`relative inline-flex rounded-full h-2 w-2 ${isRunning ? "bg-green-500" : "bg-red-500"}`}></span>
                            </span>
                            {isRunning ? "System Online" : "System Offline"}
                        </span>
                    </div>
                </div>

                <NeonButton
                    variant={isRunning ? "danger" : "primary"}
                    onClick={toggleCloneStatus}
                    className="min-w-[160px]"
                >
                    {isRunning ? (
                        <><Square className="mr-2 h-4 w-4 fill-current" /> TERMINATE</>
                    ) : (
                        <><Play className="mr-2 h-4 w-4 fill-current" /> INITIALIZE</>
                    )}
                </NeonButton>
            </motion.div>

            {/* Metrics Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <GlassCard delay={0.1}>
                    <div className="flex justify-between items-start mb-2">
                        <p className="text-sm font-medium text-muted-foreground">Total Conversations</p>
                        <MessageSquare className="h-4 w-4 text-primary" />
                    </div>
                    <div className="text-3xl font-bold text-foreground">{clone.metrics?.totalConversations || 0}</div>
                    <div className="h-[40px] mt-2 opacity-50">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={clone.metrics?.conversationsHistory || []}>
                                <Line type="monotone" dataKey="value" stroke="var(--primary)" strokeWidth={2} dot={false} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </GlassCard>

                <GlassCard delay={0.2}>
                    <div className="flex justify-between items-start mb-2">
                        <p className="text-sm font-medium text-muted-foreground">Avg. Response Time</p>
                        <Clock className="h-4 w-4 text-accent" />
                    </div>
                    <div className="text-3xl font-bold text-foreground">{clone.metrics?.avgResponseTime ? `${clone.metrics.avgResponseTime}ms` : "-"}</div>
                    <p className="text-xs text-muted-foreground mt-1">
                        {clone.metrics?.avgResponseTime ? "Optimal latency" : "Awaiting data..."}
                    </p>
                </GlassCard>

                <GlassCard delay={0.3}>
                    <div className="flex justify-between items-start mb-2">
                        <p className="text-sm font-medium text-muted-foreground">Knowledge Base</p>
                        <Activity className="h-4 w-4 text-blue-400" />
                    </div>
                    <div className="text-3xl font-bold text-foreground">{clone.datasetCount || 0}</div>
                    <p className="text-xs text-muted-foreground mt-1">Files indexed</p>
                </GlassCard>

                <GlassCard delay={0.4}>
                    <div className="flex justify-between items-start mb-2">
                        <p className="text-sm font-medium text-muted-foreground">System Health</p>
                        <Zap className="h-4 w-4 text-yellow-400" />
                    </div>
                    <div className="text-3xl font-bold text-foreground">100%</div>
                    <p className="text-xs text-green-400 mt-1">Optimal performance</p>
                </GlassCard>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                {/* Neural Network / Messengers */}
                <GlassCard delay={0.5} className="min-h-[300px]">
                    <div className="flex items-center gap-2 mb-6">
                        <Network className="h-5 w-5 text-primary" />
                        <h3 className="text-lg font-semibold">Neural Interfaces</h3>
                    </div>

                    <div className="space-y-4">
                        {clone.messengers && clone.messengers.length > 0 ? (
                            clone.messengers.map((m, i) => (
                                <motion.div
                                    key={m}
                                    initial={{ x: -20, opacity: 0 }}
                                    animate={{ x: 0, opacity: 1 }}
                                    transition={{ delay: 0.6 + (i * 0.1) }}
                                    className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/10 hover:border-primary/50 transition-colors group"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
                                        <span className="capitalize font-medium">{m}</span>
                                    </div>
                                    <div className="text-xs text-muted-foreground group-hover:text-primary transition-colors">Connected</div>
                                </motion.div>
                            ))
                        ) : (
                            <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground border border-dashed border-white/10 rounded-lg">
                                <Network className="h-8 w-8 mb-2 opacity-20" />
                                <p>No active neural links</p>
                            </div>
                        )}
                    </div>
                </GlassCard>

                {/* Deployment Terminal */}
                <GlassCard delay={0.6} className="min-h-[300px] flex flex-col">
                    <div className="flex items-center gap-2 mb-6">
                        <Terminal className="h-5 w-5 text-accent" />
                        <h3 className="text-lg font-semibold">Deployment Console</h3>
                    </div>

                    <div className="flex-1 flex flex-col gap-4">
                        <p className="text-sm text-muted-foreground">
                            Deploy this neural matrix to your local infrastructure.
                        </p>

                        {!installScript ? (
                            <div className="flex-1 flex items-center justify-center">
                                <NeonButton onClick={generateInstallScript} variant="secondary">
                                    <Terminal className="mr-2 h-4 w-4" />
                                    GENERATE SEQUENCE
                                </NeonButton>
                            </div>
                        ) : (
                            <div className="relative group flex-1">
                                <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-accent/5 rounded-lg blur-xl opacity-50" />
                                <pre className="relative h-full bg-black/80 text-green-400 p-6 rounded-lg text-xs font-mono overflow-x-auto border border-white/10 shadow-inner">
                                    <code className="break-all whitespace-pre-wrap">{installScript}</code>
                                </pre>
                                <button
                                    className="absolute top-4 right-4 p-2 rounded-md bg-white/10 hover:bg-white/20 text-white transition-colors opacity-0 group-hover:opacity-100"
                                    onClick={copyToClipboard}
                                >
                                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                                </button>
                            </div>
                        )}
                    </div>
                </GlassCard>
            </div>
        </div>
    );
}
