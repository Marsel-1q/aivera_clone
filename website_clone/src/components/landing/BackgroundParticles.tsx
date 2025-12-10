"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

export function BackgroundParticles() {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    return (
        <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none bg-black">
            {/* Background Ambience - Fixed Global */}
            <div className="absolute inset-0 z-0">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-indigo-900/20 via-black to-black opacity-80" />
            </div>

            {/* Global Animated Particles */}
            {mounted &&
                [...Array(60)].map((_, i) => (
                    <motion.div
                        key={i}
                        className="absolute w-1 h-1 bg-cyan-400/40 rounded-full blur-[1px]"
                        initial={{
                            left: `${Math.random() * 100}%`,
                            top: `${Math.random() * 100}%`,
                            scale: Math.random() * 1 + 0.5,
                            opacity: 0,
                        }}
                        animate={{
                            y: [0, Math.random() * 100 - 50, 0],
                            x: [0, Math.random() * 100 - 50, 0],
                            opacity: [0, 0.5, 0],
                        }}
                        transition={{
                            duration: 5 + Math.random() * 20,
                            repeat: Infinity,
                            ease: "easeInOut",
                            delay: Math.random() * 5,
                        }}
                    />
                ))}
        </div>
    );
}
