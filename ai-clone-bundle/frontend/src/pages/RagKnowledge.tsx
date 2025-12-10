import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { ragApi, type RagDocument } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FileText, Upload, Loader2, RefreshCw, Trash2 } from "lucide-react"
import { useRef, useState } from "react"

export default function RagKnowledge() {
    const queryClient = useQueryClient()
    const fileInputRef = useRef<HTMLInputElement>(null)
    const updateFileInputRef = useRef<HTMLInputElement>(null)
    const [isUploading, setIsUploading] = useState(false)

    const { data: documents } = useQuery({
        queryKey: ["ragDocuments"],
        queryFn: ragApi.getDocuments,
    })

    const uploadMutation = useMutation({
        mutationFn: ragApi.uploadDocument,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["ragDocuments"] })
            setIsUploading(false)
            // alert("Document uploaded successfully!")
        },
        onError: (error) => {
            console.error("Failed to upload document:", error)
            setIsUploading(false)
            alert("Failed to upload document.")
        },
    })

    const deleteMutation = useMutation({
        mutationFn: ragApi.deleteDocument,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["ragDocuments"] })
        },
        onError: (error) => {
            console.error("Failed to delete document:", error)
            alert("Failed to delete document.")
        },
    })

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setIsUploading(true)
            uploadMutation.mutate(e.target.files[0])
            e.target.value = ""
        }
    }

    const getDocLabel = (doc: RagDocument | string) => {
        if (typeof doc === 'string') return doc;
        return (
            doc?.metadata?.filename ||
            doc?.metadata?.name ||
            doc?.id
        )
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Knowledge Base</h2>
                <p className="text-muted-foreground">Manage documents for your AI clone's RAG system.</p>
            </div>

            <Tabs defaultValue="add" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="add">Add Documents</TabsTrigger>
                    <TabsTrigger value="update">Update Documents</TabsTrigger>
                </TabsList>

                <TabsContent value="add">
                    <Card>
                        <CardHeader>
                            <CardTitle>Add New Documents</CardTitle>
                            <CardDescription>
                                Upload new text files (.txt, .md) to append to your clone's knowledge base.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-10 gap-4">
                                <div className="p-4 bg-primary/10 rounded-full">
                                    <Upload className="h-8 w-8 text-primary" />
                                </div>
                                <div className="text-center">
                                    <h3 className="font-semibold text-lg">Click to upload</h3>
                                    <p className="text-sm text-muted-foreground">or drag and drop files here</p>
                                </div>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    onChange={handleFileChange}
                                    accept=".txt,.md"
                                />
                                <Button onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
                                    {isUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                                    {isUploading ? "Uploading..." : "Select File"}
                                </Button>
                                <p className="text-xs text-muted-foreground">
                                    Supported formats: .txt, .md
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="update">
                    <Card>
                        <CardHeader>
                            <CardTitle>Update Existing Documents</CardTitle>
                            <CardDescription>
                                Upload updated versions of existing documents. This will overwrite the content if the filename matches.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-10 gap-4 bg-muted/20">
                                <div className="p-4 bg-secondary rounded-full">
                                    <RefreshCw className="h-8 w-8 text-secondary-foreground" />
                                </div>
                                <div className="text-center">
                                    <h3 className="font-semibold text-lg">Upload Updated Version</h3>
                                    <p className="text-sm text-muted-foreground">Select files to replace existing ones</p>
                                </div>
                                <input
                                    type="file"
                                    ref={updateFileInputRef}
                                    className="hidden"
                                    onChange={handleFileChange}
                                    accept=".txt,.md"
                                />
                                <Button variant="secondary" onClick={() => updateFileInputRef.current?.click()} disabled={isUploading}>
                                    {isUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                                    {isUploading ? "Updating..." : "Select Update File"}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            <Card>
                <CardHeader>
                    <CardTitle>Uploaded Documents</CardTitle>
                </CardHeader>
                <CardContent>
                    {documents && documents.length > 0 ? (
                        <div className="grid gap-2">
                            {documents.map((doc, index) => (
                                <div key={typeof doc === 'string' ? index : doc.id} className="flex items-center justify-between p-3 border rounded-md bg-card hover:bg-accent/50 transition-colors">
                                    <div className="flex items-center">
                                        <FileText className="h-5 w-5 mr-3 text-primary" />
                                        <span className="text-sm font-medium">{getDocLabel(doc)}</span>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => typeof doc !== 'string' && deleteMutation.mutate(doc.id)}
                                        disabled={deleteMutation.isPending || typeof doc === 'string'}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            <FileText className="h-10 w-10 mx-auto mb-3 opacity-20" />
                            <p>No documents uploaded yet.</p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
