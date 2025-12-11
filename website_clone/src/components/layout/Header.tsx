"use client";

import { useState } from "react";
import { Bell, Search, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";

export function Header() {
    const [loggingOut, setLoggingOut] = useState(false);

    const handleLogout = async () => {
        if (loggingOut) return;
        setLoggingOut(true);
        try {
            const supabase = createClient();
            await supabase.auth.signOut();
            window.location.href = "/login";
        } catch (err) {
            console.error("Logout failed", err);
            setLoggingOut(false);
        }
    };

    return (
        <header className="flex h-16 items-center justify-between border-b border-sidebar-border bg-background px-6">
            <div className="flex items-center gap-4">
                <div className="relative w-64">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search clones, projects..."
                        className="pl-8 bg-sidebar-accent/50 border-sidebar-border focus-visible:ring-primary"
                    />
                </div>
            </div>
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
                    <Bell className="h-5 w-5" />
                </Button>
                <Button variant="outline" className="border-primary/50 text-primary hover:bg-primary/10 hover:text-primary">
                    Documentation
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground hover:text-foreground"
                    onClick={handleLogout}
                    disabled={loggingOut}
                >
                    <LogOut className="h-4 w-4 mr-2" />
                    {loggingOut ? "Logging out..." : "Logout"}
                </Button>
            </div>
        </header>
    );
}
