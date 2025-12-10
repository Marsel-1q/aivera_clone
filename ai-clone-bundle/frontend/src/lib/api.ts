import axios from "axios"

const api = axios.create({
    baseURL: "/api",
})

export interface CloneConfig {
    system_prompt: string
}

export interface TelegramBotConfig {
    bot_id: string
    token: string
    linked_clone_id: string
}

export interface TelegramConfig {
    enabled: boolean
    bots: TelegramBotConfig[]
}

export interface RagDocument {
    id: string
    metadata?: Record<string, any>
}

export const cloneApi = {
    getConfig: () => api.get<CloneConfig>("/clone").then((res) => res.data),
    updateConfig: (data: CloneConfig) => api.put("/clone", data).then((res) => res.data),
}

export const telegramApi = {
    getConfig: () => api.get<TelegramConfig>("/messengers/telegram").then((res) => res.data),
    updateConfig: (data: TelegramConfig) => api.put("/messengers/telegram", data).then((res) => res.data),
}

export const ragApi = {
    getDocuments: () => api.get<RagDocument[]>("/rag/documents").then((res) => res.data),
    uploadDocument: (file: File) => {
        const formData = new FormData()
        formData.append("file", file)
        return api.post("/rag/documents", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        }).then((res) => res.data)
    },
    deleteDocument: (id: string) => api.delete(`/rag/documents/${id}`).then((res) => res.data),
}

export const chatApi = {
    sendMessage: (message: string) => api.post<{ answer: string }>("/chat/test", { message }).then((res) => res.data),
}
