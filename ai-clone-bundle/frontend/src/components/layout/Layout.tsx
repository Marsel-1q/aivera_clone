import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"

export function Layout() {
    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-8">
                <div className="mx-auto max-w-5xl">
                    <Outlet />
                </div>
            </main>
        </div>
    )
}
