"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft, ArrowRight, Upload, Bot, Database, Sparkles, CheckCircle2, Cpu, Trash2 } from "lucide-react";
import Link from "next/link";

const steps = [
    { id: 1, name: "Model Selection", icon: Cpu },
    { id: 2, name: "Datasets", icon: Database },
    { id: 3, name: "System Prompt", icon: Bot },
    { id: 4, name: "Training", icon: Sparkles },
];

export default function CreateClonePage() {
    const router = useRouter();
    const [currentStep, setCurrentStep] = useState(1);
    const [formData, setFormData] = useState({
        name: "My Clone",
        model: "Qwen/Qwen2.5-VL-7B-Instruct",
        datasetId: "",
        datasetFiles: [] as { name: string; size: number }[],
        systemPrompt: "",
        persona: "user_persona",
    });
    const [jobId, setJobId] = useState<string | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isTraining, setIsTraining] = useState(false);
    const [statusMessage, setStatusMessage] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleNext = () => {
        if (currentStep < steps.length) {
            setCurrentStep(currentStep + 1);
        } else {
            startTraining();
        }
    };

    const handleBack = () => {
        if (currentStep > 1) {
            setCurrentStep(currentStep - 1);
        }
    };

    const handleFileSelect = async (files: FileList | null) => {
        console.log('[Upload] handleFileSelect called, files:', files);
        console.log('[Upload] Files count:', files?.length);

        if (!files || files.length === 0) {
            console.log('[Upload] No files provided, returning');
            return;
        }

        setIsUploading(true);
        setStatusMessage(null);

        let currentDatasetId = formData.datasetId;
        console.log('[Upload] Starting upload, initial datasetId:', currentDatasetId);

        try {
            const fileArray = Array.from(files);
            console.log('[Upload] Files to upload:', fileArray.map(f => f.name));

            for (const file of fileArray) {
                console.log(`[Upload] Uploading ${file.name}...`);
                const form = new FormData();
                form.append("file", file, file.name);
                if (currentDatasetId) {
                    form.append("datasetId", currentDatasetId);
                    console.log(`[Upload] Using existing datasetId: ${currentDatasetId}`);
                } else {
                    console.log('[Upload] No datasetId, will create new one');
                }

                const res = await fetch("/api/datasets", {
                    method: "POST",
                    body: form,
                });

                console.log(`[Upload] Response status for ${file.name}:`, res.status);

                if (!res.ok) {
                    const errorText = await res.text();
                    console.error(`[Upload] Upload failed for ${file.name}:`, errorText);
                    throw new Error(`Upload failed for ${file.name}: ${res.status}`);
                }

                const data = await res.json();
                console.log(`[Upload] Response data for ${file.name}:`, data);
                currentDatasetId = data.datasetId;

                setFormData((prev) => ({
                    ...prev,
                    datasetId: data.datasetId,
                    datasetFiles: data.files || [],
                }));
                console.log(`[Upload] Updated state with ${data.files?.length || 0} files`);
            }
            setStatusMessage("Dataset uploaded");
            console.log('[Upload] All files uploaded successfully');

            // Reset the file input
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
                console.log('[Upload] Input reset');
            }
        } catch (e) {
            console.error('[Upload] Error during upload:', e);
            setStatusMessage("Failed to upload some files");
        } finally {
            setIsUploading(false);
            console.log('[Upload] Upload process finished');
        }
    };

    const handleDeleteFile = async (filename: string) => {
        if (!formData.datasetId) return;

        try {
            const res = await fetch(`/api/datasets?datasetId=${formData.datasetId}&filename=${encodeURIComponent(filename)}`, {
                method: "DELETE",
            });

            if (!res.ok) {
                throw new Error("Failed to delete file");
            }

            const data = await res.json();
            setFormData((prev) => ({
                ...prev,
                datasetFiles: data.files || [],
            }));
        } catch (e) {
            console.error(e);
            setStatusMessage("Failed to delete file");
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const startTraining = async () => {
        if (isTraining) return;
        setIsTraining(true);
        setStatusMessage(null);
        try {
            const res = await fetch("/api/training", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    modelId: formData.model,
                    datasetId: formData.datasetId,
                    systemPrompt: formData.systemPrompt,
                    persona: formData.persona,
                    cloneName: formData.name,
                }),
            });
            if (!res.ok) {
                throw new Error(`Training start failed: ${res.status}`);
            }
            const data = await res.json();
            setJobId(data.jobId);
            setStatusMessage("Training started");
            // persist jobId so it survives navigation/reload
            if (typeof window !== "undefined" && data.jobId) {
                localStorage.setItem("activeTrainingJobId", data.jobId);
            }
            router.push(`/clones?training=true&jobId=${data.jobId || ""}`);
        } catch (e) {
            console.error(e);
            setStatusMessage("Failed to start training");
        } finally {
            setIsTraining(false);
        }
    };

    return (
        <div className="max-w-4xl mx-auto py-8 space-y-8">
            {/* Header */}
            <div className="flex items-center space-x-4">
                <Link href="/clones">
                    <Button variant="ghost" size="icon">
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                </Link>
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Create New Clone</h1>
                    <p className="text-muted-foreground">Train a new AI model with your custom data.</p>
                </div>
            </div>

            {/* Progress Steps */}
            <div className="relative">
                <div className="absolute top-1/2 left-0 w-full h-0.5 bg-border -z-10" />
                <div className="flex justify-between">
                    {steps.map((step) => {
                        const Icon = step.icon;
                        const isActive = step.id === currentStep;
                        const isCompleted = step.id < currentStep;

                        return (
                            <div key={step.id} className="flex flex-col items-center bg-background px-4">
                                <div
                                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors ${isActive
                                        ? "border-primary bg-primary text-primary-foreground"
                                        : isCompleted
                                            ? "border-primary bg-primary/20 text-primary"
                                            : "border-muted-foreground/30 text-muted-foreground"
                                        }`}
                                >
                                    {isCompleted ? <CheckCircle2 className="h-6 w-6" /> : <Icon className="h-5 w-5" />}
                                </div>
                                <span
                                    className={`mt-2 text-sm font-medium ${isActive ? "text-primary" : "text-muted-foreground"
                                        }`}
                                >
                                    {step.name}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Step Content */}
            <Card className="min-h-[400px] flex flex-col bg-card/50 backdrop-blur-sm border-primary/20">
                <CardContent className="flex-1 p-8">
                    {currentStep === 1 && (
                        <div className="space-y-6">
                            <div className="text-center space-y-2">
                                <h2 className="text-xl font-semibold">Select Base Model</h2>
                                <p className="text-muted-foreground">Choose the architecture for your clone.</p>
                            </div>
                            <div className="space-y-2">
                                <Label>Clone Name</Label>
                                <Input
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="My Clone"
                                />
                            </div>
                            <div className="grid gap-4 md:grid-cols-2">
                                <div
                                    className={`p-6 rounded-xl border-2 cursor-pointer transition-all ${formData.model === "Qwen/Qwen2.5-VL-7B-Instruct"
                                        ? "border-primary bg-primary/10 shadow-[0_0_20px_rgba(124,58,237,0.2)]"
                                        : "border-border hover:border-primary/50"
                                        }`}
                                    onClick={() => setFormData({ ...formData, model: "Qwen/Qwen2.5-VL-7B-Instruct" })}
                                >
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="p-2 bg-blue-500/20 rounded-lg">
                                            <Cpu className="h-6 w-6 text-blue-500" />
                                        </div>
                                        {formData.model === "Qwen/Qwen2.5-VL-7B-Instruct" && (
                                            <CheckCircle2 className="h-5 w-5 text-primary" />
                                        )}
                                    </div>
                                    <h3 className="font-bold text-lg">Qwen 2.5 VL</h3>
                                    <p className="text-sm text-muted-foreground mt-2">
                                        7B Parameters • Vision-Language • Instruct Tuned
                                    </p>
                                    <div className="mt-4 flex gap-2">
                                        <span className="text-xs bg-secondary px-2 py-1 rounded-full">Fast</span>
                                        <span className="text-xs bg-secondary px-2 py-1 rounded-full">Multimodal</span>
                                    </div>
                                </div>
                                {/* Placeholder for future models */}
                                <div className="p-6 rounded-xl border-2 border-border/50 opacity-50 cursor-not-allowed">
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="p-2 bg-gray-500/20 rounded-lg">
                                            <Cpu className="h-6 w-6 text-gray-500" />
                                        </div>
                                    </div>
                                    <h3 className="font-bold text-lg">Llama 3 70B</h3>
                                    <p className="text-sm text-muted-foreground mt-2">Coming Soon</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {currentStep === 2 && (
                        <div className="space-y-6">
                            <div className="text-center space-y-2">
                                <h2 className="text-xl font-semibold">Upload Knowledge Base</h2>
                                <p className="text-muted-foreground">Upload chats, documents, and images for training.</p>
                            </div>
                            <div
                                className="border-2 border-dashed border-border rounded-xl p-12 flex flex-col items-center justify-center text-center hover:border-primary/50 transition-colors cursor-pointer bg-muted/20"
                                onDrop={handleDrop}
                                onDragOver={handleDragOver}
                                onClick={() => {
                                    console.log('[Upload] Drop zone clicked');
                                    fileInputRef.current?.click();
                                }}
                            >
                                <div className="p-4 bg-primary/10 rounded-full mb-4">
                                    <Upload className="h-8 w-8 text-primary" />
                                </div>
                                <h3 className="font-medium text-lg">Drag & Drop files here</h3>
                                <p className="text-sm text-muted-foreground mt-2">
                                    Supports .txt, .pdf, .json, .jpg, .png (Max 50MB)
                                </p>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    multiple
                                    className="hidden"
                                    onChange={(e) => {
                                        console.log('[Upload] Input onChange fired', e.target.files);
                                        handleFileSelect(e.target.files);
                                    }}
                                />
                                <Button
                                    variant="outline"
                                    className="mt-6"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        console.log('[Upload] Browse button clicked');
                                        fileInputRef.current?.click();
                                    }}
                                    disabled={isUploading}
                                >
                                    {isUploading ? "Uploading..." : "Browse Files"}
                                </Button>
                            </div>
                            <div className="space-y-2">
                                <p className="text-sm font-medium">
                                    Uploaded Files ({formData.datasetFiles.length})
                                </p>
                                {formData.datasetFiles.length > 0 ? (
                                    <div className="text-sm text-foreground space-y-1">
                                        {formData.datasetFiles.map((f) => (
                                            <div key={f.name} className="flex justify-between items-center border rounded px-3 py-2 bg-background">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium text-sm">{f.name}</span>
                                                    <span className="text-muted-foreground text-xs">({(f.size / 1024).toFixed(1)} KB)</span>
                                                </div>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 text-muted-foreground hover:text-red-500"
                                                    onClick={() => handleDeleteFile(f.name)}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-sm text-muted-foreground italic">No files uploaded yet.</div>
                                )}
                            </div>
                            {statusMessage && (
                                <p className={`text-xs ${statusMessage.includes("Failed") ? "text-red-500" : "text-muted-foreground"}`}>
                                    {statusMessage}
                                </p>
                            )}
                        </div>
                    )}

                    {currentStep === 3 && (
                        <div className="space-y-6">
                            <div className="text-center space-y-2">
                                <h2 className="text-xl font-semibold">Define Persona</h2>
                                <p className="text-muted-foreground">Set the system prompt and behavior rules.</p>
                            </div>
                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <Label>Persona ID</Label>
                                    <Input
                                        value={formData.persona}
                                        onChange={(e) => setFormData({ ...formData, persona: e.target.value })}
                                        placeholder="user_persona"
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Это имя персоны для подготовки датасета (аргумент --persona в pipeline).
                                    </p>
                                </div>
                                <div className="space-y-2">
                                    <Label>System Prompt</Label>
                                    <Textarea
                                        placeholder="You are a helpful AI assistant..."
                                        className="min-h-[200px] font-mono"
                                        value={formData.systemPrompt}
                                        onChange={(e) => setFormData({ ...formData, systemPrompt: e.target.value })}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Describe who the AI is, what it knows, and how it should behave.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {currentStep === 4 && (
                        <div className="space-y-6">
                            <div className="text-center space-y-2">
                                <h2 className="text-xl font-semibold">Ready to Train</h2>
                                <p className="text-muted-foreground">Review your configuration and start training.</p>
                            </div>
                            <div className="bg-muted/30 rounded-xl p-6 space-y-4 border border-border">
                                <div className="flex justify-between py-2 border-b border-border/50">
                                    <span className="text-muted-foreground">Base Model</span>
                                    <span className="font-medium">{formData.model}</span>
                                </div>
                                <div className="flex justify-between py-2 border-b border-border/50">
                                    <span className="text-muted-foreground">Dataset Size</span>
                                    <span className="font-medium">
                                        {formData.datasetFiles.length} file{formData.datasetFiles.length === 1 ? "" : "s"}
                                    </span>
                                </div>
                                <div className="flex justify-between py-2 border-b border-border/50">
                                    <span className="text-muted-foreground">Persona</span>
                                    <span className="font-medium">{formData.persona || "user_persona"}</span>
                                </div>
                                <div className="flex justify-between py-2 border-b border-border/50">
                                    <span className="text-muted-foreground">System Prompt</span>
                                    <span className="font-medium">{formData.systemPrompt ? "Configured" : "Empty"}</span>
                                </div>
                                <div className="flex justify-between py-2">
                                    <span className="text-muted-foreground">Estimated Time</span>
                                    <span className="font-medium text-primary">~15 minutes</span>
                                </div>
                            </div>
                        </div>
                    )}
                </CardContent>
                <CardFooter className="flex justify-between p-8 pt-0">
                    <Button
                        variant="outline"
                        onClick={handleBack}
                        disabled={currentStep === 1}
                    >
                        Back
                    </Button>
                    <Button
                        onClick={handleNext}
                        className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_20px_rgba(124,58,237,0.3)]"
                        disabled={
                            isUploading ||
                            (currentStep === 2 && !formData.datasetId) ||
                            (currentStep === steps.length && (isTraining || !formData.datasetId))
                        }
                    >
                        {currentStep === steps.length ? (
                            <>
                                {isTraining ? "Starting..." : "Start Training"} <Sparkles className="ml-2 h-4 w-4" />
                            </>
                        ) : (
                            <>
                                Next Step <ArrowRight className="ml-2 h-4 w-4" />
                            </>
                        )}
                    </Button>
                </CardFooter>
            </Card>
        </div>
    );
}
