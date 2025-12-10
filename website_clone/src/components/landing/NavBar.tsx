"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";

export function NavBar() {
    return (
        <motion.nav
            initial={{ y: -100 }}
            animate={{ y: 0 }}
            transition={{ duration: 0.5 }}
            className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 bg-black/20 backdrop-blur-md border-b border-white/10"
        >
            <div className="flex items-center gap-2">
                <Link href="/" className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-cyan-400">
                    AIVERA
                </Link>
            </div>

            <div className="flex items-center gap-4">
                <Link href="/login">
                    <Button variant="ghost" className="text-gray-300 hover:text-white hover:bg-white/10">
                        Log In
                    </Button>
                </Link>
                <Link href="/signup">
                    <Button className="bg-cyan-600 hover:bg-cyan-500 text-white shadow-[0_0_15px_rgba(8,145,178,0.4)]">
                        Sign Up
                    </Button>
                </Link>
            </div>
        </motion.nav>
    );
}
