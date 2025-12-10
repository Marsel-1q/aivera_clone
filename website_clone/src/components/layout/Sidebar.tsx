"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    Users,
    Folder,
    Database,
    Zap,
    TestTube,
    Rocket,
    Settings,
    LayoutDashboard,
} from "lucide-react";

const navigation = [
    { name: "Overview", href: "/dashboard", icon: LayoutDashboard },
    { name: "Clones", href: "/clones", icon: Users },
    { name: "Projects", href: "/projects", icon: Folder },
    { name: "Datasets", href: "/datasets", icon: Database },
    { name: "Training", href: "/training", icon: Zap },
    { name: "Tests", href: "/tests", icon: TestTube },
    { name: "Deploy", href: "/deploy", icon: Rocket },
    { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="flex h-full w-64 flex-col bg-sidebar border-r border-sidebar-border">
            <div className="flex h-16 items-center px-6 border-b border-sidebar-border">
                <span className="text-xl font-bold text-primary tracking-wider">
                    AIVERA
                </span>
            </div>
            <div className="flex-1 overflow-y-auto py-4">
                <nav className="space-y-1 px-3">
                    {navigation.map((item) => {
                        const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
                        return (
                            <Link
                                key={item.name}
                                href={item.href}
                                className={cn(
                                    "group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors",
                                    isActive
                                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                                        : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                                )}
                            >
                                <item.icon
                                    className={cn(
                                        "mr-3 h-5 w-5 flex-shrink-0",
                                        isActive
                                            ? "text-primary"
                                            : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground"
                                    )}
                                    aria-hidden="true"
                                />
                                {item.name}
                            </Link>
                        );
                    })}
                </nav>
            </div>
            <div className="p-4 border-t border-sidebar-border">
                <div className="flex items-center">
                    <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-xs">
                        JD
                    </div>
                    <div className="ml-3">
                        <p className="text-sm font-medium text-sidebar-foreground">John Doe</p>
                        <p className="text-xs text-sidebar-foreground/50">Pro Plan</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
