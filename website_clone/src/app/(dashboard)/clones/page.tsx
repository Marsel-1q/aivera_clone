"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, User } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";

function ClonesContent() {
    const [clones, setClones] = useState<
        Array<{ id: string; name: string; status: string; modelId: string; datasetCount?: number; startedAt?: number; updatedAt?: number }>
    >([]);

    useEffect(() => {
        const loadClones = async () => {
            try {
                const res = await fetch("/api/clones");
                if (!res.ok) return;
                const data = await res.json();
                setClones(Array.isArray(data) ? data : (data.clones || []));
            } catch (err) {
                console.error("Failed to load clones", err);
            }
        };
        loadClones();
        const id = setInterval(loadClones, 5000);
        return () => clearInterval(id);
    }, []);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight">My Clones</h1>
                <Link href="/clones/new">
                    <Button className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(124,58,237,0.5)]">
                        <Plus className="mr-2 h-4 w-4" /> Create Clone
                    </Button>
                </Link>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {/* Clones from backend */}
                {clones.map((clone) => (
                    <Card key={clone.id} className="bg-card border-border/50 hover:border-primary/50 transition-colors cursor-pointer group">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-lg font-medium">{clone.name}</CardTitle>
                            <div className={`h-2 w-2 rounded-full ${clone.status === "ready" ? "bg-green-500" : clone.status === "failed" ? "bg-red-500" : "bg-amber-500"} ${clone.status === "ready" ? "animate-pulse" : ""}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center gap-4 mb-4">
                                <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center">
                                    <User className="h-6 w-6 text-primary" />
                                </div>
                                <div className="text-sm text-muted-foreground space-y-1">
                                    <p className="font-medium text-foreground">{clone.name}</p>
                                    <p>Status: {clone.status}</p>
                                    <p>Model: {clone.modelId}</p>
                                    {clone.datasetCount !== undefined && <p>Datasets: {clone.datasetCount}</p>}
                                    {clone.startedAt && (
                                        <p>Started: {new Date(clone.startedAt).toLocaleString()}</p>
                                    )}
                                    {clone.updatedAt && (
                                        <p className="text-xs text-muted-foreground">Updated: {new Date(clone.updatedAt).toLocaleString()}</p>
                                    )}
                                </div>
                            </div>
                            <div className="flex justify-between items-center mt-4">
                                <span className="text-xs bg-secondary px-2 py-1 rounded-full">Clone</span>
                                <Link href={`/clones/${clone.id}`}>
                                    <Button variant="ghost" size="sm" className="group-hover:text-primary">Open Studio →</Button>
                                </Link>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}

export default function ClonesPage() {
    return (
        <Suspense fallback={<div>Loading...</div>}>
            <ClonesContent />
        </Suspense>
    );
}
