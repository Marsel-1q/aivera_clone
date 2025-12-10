"use client";

import { motion } from "framer-motion";
import { Server, Cloud, ArrowRight, Database } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LocalNodes() {
    return (
        <section className="py-24 relative overflow-hidden z-10">
            {/* Background Decor */}
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-900/20 rounded-full blur-[100px]" />

            <div className="container mx-auto px-4 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

                <motion.div
                    initial={{ opacity: 0, x: -30 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                >
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/50 border border-indigo-500/30 text-indigo-300 text-sm font-medium mb-6">
                        <Server className="w-4 h-4" />
                        <span>On-Premise Solution</span>
                    </div>

                    <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
                        Ваши данные — <br />
                        <span className="text-indigo-400">Ваши правила</span>
                    </h2>

                    <p className="text-gray-400 text-lg mb-8 leading-relaxed">
                        Мы понимаем важность приватности. Обучите модель в нашем защищенном облаке,
                        а затем выгрузите её на свой локальный сервер или ноутбук. Клон будет работать
                        полностью автономно, без отправки данных наружу.
                    </p>

                    <Button variant="outline" className="border-indigo-500/50 text-indigo-300 hover:bg-indigo-950 hover:text-white">
                        Документация по развёртыванию
                        <ArrowRight className="ml-2 w-4 h-4" />
                    </Button>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    className="relative"
                >
                    <div className="relative z-10 p-8 rounded-2xl bg-zinc-900/50 border border-white/10 backdrop-blur-xl">
                        <div className="flex items-center justify-between mb-8">
                            <div className="text-center">
                                <div className="w-16 h-16 bg-blue-900/30 rounded-xl flex items-center justify-center mx-auto mb-2 border border-blue-500/30">
                                    <Cloud className="w-8 h-8 text-blue-400" />
                                </div>
                                <p className="text-sm text-gray-400">Cloud Training</p>
                            </div>

                            <div className="flex-1 h-px bg-gradient-to-r from-blue-500/20 via-indigo-500/50 to-purple-500/20 mx-4 relative">
                                <motion.div
                                    animate={{ x: [-10, 100], opacity: [0, 1, 0] }}
                                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                                    className="absolute top-1/2 -translate-y-1/2 w-4 h-1 bg-white shadow-[0_0_10px_white] rounded-full"
                                />
                            </div>

                            <div className="text-center">
                                <div className="w-16 h-16 bg-purple-900/30 rounded-xl flex items-center justify-center mx-auto mb-2 border border-purple-500/30">
                                    <Database className="w-8 h-8 text-purple-400" />
                                </div>
                                <p className="text-sm text-gray-400">Local Node</p>
                            </div>
                        </div>

                        <div className="space-y-3 font-mono text-sm text-green-400/80 bg-black/50 p-4 rounded-lg border border-white/5">
                            <p>{'>'} downloading_model_weights...</p>
                            <p>{'>'} verifying_checksum... OK</p>
                            <p>{'>'} starting_inference_engine...</p>
                            <p className="text-green-400 animate-pulse">{'>'} local_node_ready_</p>
                        </div>
                    </div>
                </motion.div>

            </div>
        </section>
    );
}
