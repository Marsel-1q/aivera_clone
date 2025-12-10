"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

interface NeonButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    children: React.ReactNode;
    variant?: "primary" | "secondary" | "danger";
    isLoading?: boolean;
    className?: string;
}

export function NeonButton({
    children,
    variant = "primary",
    isLoading,
    className,
    ...props
}: NeonButtonProps) {
    const variants = {
        primary: "bg-primary text-primary-foreground shadow-[0_0_20px_rgba(var(--primary),0.5)] hover:shadow-[0_0_30px_rgba(var(--primary),0.8)] border-primary/50",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80 border-secondary/50",
        danger: "bg-destructive text-destructive-foreground shadow-[0_0_20px_rgba(var(--destructive),0.5)] hover:shadow-[0_0_30px_rgba(var(--destructive),0.8)] border-destructive/50",
    };

    return (
        <motion.div
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
        >
            <Button
                className={cn(
                    "relative overflow-hidden transition-all duration-300 border",
                    variants[variant],
                    className
                )}
                disabled={isLoading || props.disabled}
                {...props}
            >
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {children}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-[200%] animate-[shimmer_2s_infinite]" />
            </Button>
        </motion.div>
    );
}
