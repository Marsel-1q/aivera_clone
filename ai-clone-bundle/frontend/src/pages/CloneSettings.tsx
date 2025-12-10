import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { cloneApi } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useState, useEffect } from "react"

export default function CloneSettings() {
    const queryClient = useQueryClient()
    const [systemPrompt, setSystemPrompt] = useState("")

    const { data: config } = useQuery({
        queryKey: ["cloneConfig"],
        queryFn: cloneApi.getConfig,
    })

    useEffect(() => {
        if (config) {
            setSystemPrompt(config.system_prompt)
        }
    }, [config])

    const mutation = useMutation({
        mutationFn: cloneApi.updateConfig,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloneConfig"] })
            alert("Settings saved successfully!")
        },
        onError: (error) => {
            console.error("Failed to save settings:", error)
            alert("Failed to save settings.")
        },
    })

    const handleSave = () => {
        mutation.mutate({ system_prompt: systemPrompt })
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Clone Settings</h2>
                <p className="text-muted-foreground">Configure your AI clone's personality and behavior.</p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>System Prompt</CardTitle>
                    <CardDescription>
                        The system prompt defines how your AI clone behaves and responds.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Textarea
                        value={systemPrompt}
                        onChange={(e) => setSystemPrompt(e.target.value)}
                        rows={10}
                        placeholder="You are a helpful AI assistant..."
                    />
                    <div className="flex justify-end">
                        <Button onClick={handleSave} disabled={mutation.isPending}>
                            {mutation.isPending ? "Saving..." : "Save Changes"}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
