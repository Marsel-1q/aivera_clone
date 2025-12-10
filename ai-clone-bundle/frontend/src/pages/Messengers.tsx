import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { telegramApi, type TelegramBotConfig } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { useState, useEffect } from "react"

export default function Messengers() {
    const queryClient = useQueryClient()
    const [enabled, setEnabled] = useState(false)
    const [botToken, setBotToken] = useState("")

    const { data: config } = useQuery({
        queryKey: ["telegramConfig"],
        queryFn: telegramApi.getConfig,
    })

    useEffect(() => {
        if (config) {
            setEnabled(config.enabled)
            if (config.bots && config.bots.length > 0) {
                setBotToken(config.bots[0].token)
            }
        }
    }, [config])

    const mutation = useMutation({
        mutationFn: telegramApi.updateConfig,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["telegramConfig"] })
            alert("Telegram config saved!")
        },
        onError: (error) => {
            console.error("Failed to save telegram config:", error)
            alert("Failed to save config.")
        },
    })

    const handleSave = () => {
        const bots: TelegramBotConfig[] = botToken
            ? [{ bot_id: "default", token: botToken, linked_clone_id: "default" }]
            : []

        mutation.mutate({ enabled, bots })
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Messengers</h2>
                <p className="text-muted-foreground">Connect your AI clone to messaging platforms.</p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Telegram Integration</CardTitle>
                    <CardDescription>
                        Enable Telegram bot to let users chat with your clone via Telegram.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="flex items-center space-x-2">
                        <Switch id="telegram-enabled" checked={enabled} onCheckedChange={setEnabled} />
                        <Label htmlFor="telegram-enabled">Enable Telegram Bot</Label>
                    </div>

                    {enabled && (
                        <div className="space-y-2">
                            <Label htmlFor="bot-token">Bot Token</Label>
                            <Input
                                id="bot-token"
                                value={botToken}
                                onChange={(e) => setBotToken(e.target.value)}
                                placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                            />
                            <p className="text-xs text-muted-foreground">
                                Get your token from <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="underline">@BotFather</a>.
                            </p>
                        </div>
                    )}

                    <div className="flex justify-end">
                        <Button onClick={handleSave} disabled={mutation.isPending}>
                            {mutation.isPending ? "Saving..." : "Save Configuration"}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
