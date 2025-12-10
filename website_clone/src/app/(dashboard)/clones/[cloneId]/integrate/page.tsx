"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Check, X, MessageCircle, Bot, Slack, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import type { IntegrationConfig } from "@/lib/integrationStore";

type Platform = "telegram" | "whatsapp" | "google" | "slack";

const platforms: { id: Platform; name: string; description: string; icon: React.ComponentType<any>; accent: string }[] = [
    { id: "telegram", name: "Telegram", description: "Bot API", icon: MessageCircle, accent: "text-blue-400" },
    { id: "whatsapp", name: "WhatsApp", description: "Business API", icon: MessageCircle, accent: "text-green-400" },
    { id: "google", name: "Google", description: "Workspace", icon: Globe, accent: "text-amber-400" },
    { id: "slack", name: "Slack", description: "Workspace App", icon: Slack, accent: "text-pink-400" },
];

export default function CloneIntegratePage() {
    const params = useParams();
    const cloneId = params.cloneId as string;
    const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
    const [loading, setLoading] = useState(true);
    const [editTelegram, setEditTelegram] = useState(false);
    const [telegramToken, setTelegramToken] = useState("");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = async () => {
        try {
            const res = await fetch(`/api/clones/${cloneId}/integrations`);
            if (res.ok) {
                const data = await res.json();
                setIntegrations(data.integrations || []);
                const tg = (data.integrations || []).find((i: IntegrationConfig) => i.platform === "telegram");
                if (tg?.token) setTelegramToken(tg.token);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [cloneId]);

    const integrationState = (platform: Platform) => integrations.find((i) => i.platform === platform);

    const saveTelegram = async (opts: { token?: string; active?: boolean }) => {
        setSaving(true);
        setError(null);
        try {
            const res = await fetch(`/api/clones/${cloneId}/integrations/telegram`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(opts),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.error || "Failed to update Telegram");
            } else {
                setIntegrations(data.integrations || []);
                const tg = (data.integrations || []).find((i: IntegrationConfig) => i.platform === "telegram");
                if (tg?.token) setTelegramToken(tg.token);
                setEditTelegram(false);
            }
        } catch (e: any) {
            setError(e?.message || "Failed to update Telegram");
        } finally {
            setSaving(false);
        }
    };

    const renderPlatformRow = (platform: typeof platforms[number]) => {
        const state = integrationState(platform.id);
        const Icon = platform.icon;
        const isTelegram = platform.id === "telegram";
        return (
            <div key={platform.id} className="flex items-start justify-between py-3 border-b border-border/50 last:border-b-0">
                <div className="flex items-center gap-3">
                    <div className={cn("p-3 rounded-full bg-muted/40", platform.accent.replace("text", "bg"))}>
                        <Icon className={cn("h-6 w-6", platform.accent)} />
                    </div>
                    <div>
                        <p className="font-semibold">{platform.name}</p>
                        <p className="text-xs text-muted-foreground">{platform.description}</p>
                        {isTelegram && editTelegram && (
                            <div className="mt-3 flex items-center gap-2">
                                <Input
                                    placeholder="Bot token (123456:ABC-DEF...)"
                                    value={telegramToken}
                                    onChange={(e) => setTelegramToken(e.target.value)}
                                    className="max-w-sm"
                                />
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    disabled={saving}
                                    onClick={() => {
                                        setEditTelegram(false);
                                        setError(null);
                                    }}
                                >
                                    <X className="h-4 w-4" />
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    disabled={saving || !telegramToken.trim()}
                                    onClick={() => saveTelegram({ token: telegramToken })}
                                >
                                    <Check className="h-4 w-4" />
                                </Button>
                            </div>
                        )}
                        {isTelegram && !editTelegram && state?.token && (
                            <p className="text-xs text-muted-foreground mt-1">
                                Token saved • updated {state.updatedAt ? new Date(state.updatedAt).toLocaleString() : ""}
                            </p>
                        )}
                        {error && isTelegram && (
                            <p className="text-xs text-red-400 mt-1">{error}</p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Switch
                        checked={!!state?.active}
                        onCheckedChange={(checked) => {
                            if (isTelegram) {
                                saveTelegram({ active: checked });
                            }
                        }}
                        disabled={isTelegram ? saving : true}
                    />
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                            if (isTelegram) {
                                setEditTelegram((prev) => !prev);
                            }
                        }}
                        disabled={!isTelegram}
                    >
                        Configure
                    </Button>
                </div>
            </div>
        );
    };

    if (loading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-medium">Integrate</h2>
                <p className="text-sm text-muted-foreground">Connect your clone to messaging platforms.</p>
            </div>

            <Card className="bg-card/50 backdrop-blur-sm border-primary/20">
                <CardHeader>
                    <CardTitle>Messaging Platforms</CardTitle>
                    <CardDescription>Configure and activate integrations.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                    {platforms.map(renderPlatformRow)}
                </CardContent>
            </Card>
        </div>
    );
}
