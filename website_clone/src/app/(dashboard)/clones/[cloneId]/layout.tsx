"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Settings, Share2 } from "lucide-react";

const tabs = [
    { name: "Overview", href: "" },
    { name: "Data", href: "/data" },
    { name: "Behavior", href: "/behavior" },
    { name: "Tests", href: "/tests" },
    { name: "Integrate", href: "/integrate" },
];

export default function CloneLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const params = useParams();
    const cloneId = params.cloneId as string;
    const baseUrl = `/clones/${cloneId}`;

    return (
        <div className="flex flex-col h-full space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                    <Link href="/clones">
                        <Button variant="ghost" size="icon">
                            <ArrowLeft className="h-4 w-4" />
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Clone Studio</h1>
                        <p className="text-sm text-muted-foreground">ID: {cloneId}</p>
                    </div>
                </div>
                <div className="flex items-center space-x-2">
                    <Button variant="outline" size="sm">
                        <Share2 className="mr-2 h-4 w-4" />
                        Share
                    </Button>
                    <Button variant="outline" size="sm">
                        <Settings className="mr-2 h-4 w-4" />
                        Settings
                    </Button>
                </div>
            </div>

            {/* Tabs Navigation */}
            <div className="border-b border-border">
                <nav className="-mb-px flex space-x-8" aria-label="Tabs">
                    {tabs.map((tab) => {
                        const href = `${baseUrl}${tab.href}`;
                        const isActive = pathname === href;

                        return (
                            <Link
                                key={tab.name}
                                href={href}
                                className={cn(
                                    isActive
                                        ? "border-primary text-primary"
                                        : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                                    "whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium transition-colors"
                                )}
                            >
                                {tab.name}
                            </Link>
                        );
                    })}
                </nav>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
                {children}
            </div>
        </div>
    );
}
