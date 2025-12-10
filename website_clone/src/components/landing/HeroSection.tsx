"use client";

import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Lock, Cpu, Sparkles } from "lucide-react";


export function HeroSection() {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    return (
        <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden text-white">

            <div className="container relative z-10 px-4 pt-20 md:pt-0 mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
                {/* Left Content */}
                <motion.div
                    initial={{ opacity: 0, x: -50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="space-y-8"
                >
                    <div className="space-y-4">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2, duration: 0.8 }}
                            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/50 border border-indigo-500/30 text-indigo-300 text-sm font-medium"
                        >
                            <Sparkles className="w-4 h-4 text-cyan-400" />
                            <span>Next Gen Digital Cloning</span>
                        </motion.div>

                        <h1 className="text-5xl md:text-7xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-cyan-100 to-indigo-200">
                            Личные AI-двойники, <br />
                            <span className="text-cyan-400">а не просто боты</span>
                        </h1>

                        <p className="text-xl md:text-2xl text-gray-400 max-w-xl leading-relaxed">
                            Загрузи реальные диалоги — получи клона, который ведёт себя, думает и шутит точь-в-точь как оригинал.
                        </p>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-4">
                        <Button
                            size="lg"
                            asChild
                            className="bg-cyan-600 hover:bg-cyan-500 text-white border-0 shadow-[0_0_20px_rgba(8,145,178,0.5)] transition-all duration-300 transform hover:scale-105"
                        >
                            <Link href="/clones/new">
                                Создать первого клона
                                <ArrowRight className="ml-2 w-5 h-5" />
                            </Link>
                        </Button>

                        <Button
                            size="lg"
                            variant="outline"
                            className="border-indigo-500/30 text-indigo-100 hover:bg-indigo-950/30 hover:text-white transition-all"
                        >
                            Посмотреть демо
                        </Button>
                    </div>

                    {/* Trust Badges */}
                    <div className="flex flex-wrap gap-6 pt-4 text-sm text-gray-500 font-mono">
                        <div className="flex items-center gap-2">
                            <Cpu className="w-4 h-4 text-purple-400" />
                            <span>100% Local Inference</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Lock className="w-4 h-4 text-purple-400" />
                            <span>Private Data</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-purple-400" />
                            <span>Realistic Behavior</span>
                        </div>
                    </div>
                </motion.div>

                {/* Right Visual - Digital Brain */}
                <div className="relative h-[500px] w-full flex items-center justify-center">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 1, delay: 0.2 }}
                        className="relative w-full h-full max-w-[600px]"
                    >


                        {/* Orbiting Circles */}
                        <motion.div
                            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] rounded-full border border-cyan-500/10 z-0"
                            animate={{ rotate: 360 }}
                            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                        />
                        <motion.div
                            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[90%] h-[90%] rounded-full border border-purple-500/10 z-0"
                            animate={{ rotate: -360 }}
                            transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                        />
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
