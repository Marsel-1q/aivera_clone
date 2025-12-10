import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { MessageSquare, Settings, Database, Share2, Bot } from "lucide-react"

const navItems = [
    {
        title: "Test Chat",
        href: "/",
        icon: MessageSquare,
    },
    {
        title: "Clone Settings",
        href: "/settings",
        icon: Settings,
    },
    {
        title: "Knowledge Base",
        href: "/rag",
        icon: Database,
    },
    {
        title: "Messengers",
        href: "/messengers",
        icon: Share2,
    },
]

export function Sidebar() {
    return (
        <div className="flex h-screen w-64 flex-col border-r bg-card">
            <div className="p-6">
                <div className="flex items-center gap-2 font-bold text-xl text-primary">
                    <Bot className="h-6 w-6" />
                    <span>AI Clone</span>
                </div>
            </div>
            <nav className="flex-1 px-4 space-y-2">
                {navItems.map((item) => (
                    <NavLink
                        key={item.href}
                        to={item.href}
                        className={({ isActive }) =>
                            cn(
                                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all hover:text-primary",
                                isActive
                                    ? "bg-secondary text-primary"
                                    : "text-muted-foreground hover:bg-secondary/50"
                            )
                        }
                    >
                        <item.icon className="h-4 w-4" />
                        {item.title}
                    </NavLink>
                ))}
            </nav>
            <div className="p-4 border-t text-xs text-muted-foreground text-center">
                v1.0.0
            </div>
        </div>
    )
}
