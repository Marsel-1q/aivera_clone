"use client";

import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";

const audiences = [
    {
        title: "Creators & Influencers",
        description: "Масштабируйте ваше общение с фанатами, не теряя личного тона.",
        features: ["Персональные ответы", "Сохранение TOV", "Работа 24/7"],
    },
    {
        title: "HR & Эксперты",
        description: "Автоматизируйте онбординг и ответы на частые вопросы с вашей экспертизой.",
        features: ["База знаний", "Обучение новичков", "Менторство"],
    },
    {
        title: "Founders & Platforms",
        description: "Создавайте умных NPC для игр или агентов поддержки нового поколения.",
        features: ["API интеграция", "Низкая задержка", "Кастомные сценарии"],
    },
];

export function TargetAudience() {
    return (
        <section className="py-24 border-y border-white/5 relative z-10">
            <div className="container mx-auto px-4">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center mb-16"
                >
                    <h2 className="text-3xl md:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                        Для кого это?
                    </h2>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {audiences.map((item, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, scale: 0.95 }}
                            whileInView={{ opacity: 1, scale: 1 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className="p-8 rounded-2xl bg-white/5 border border-white/10 hover:border-cyan-500/30 transition-all hover:shadow-[0_0_30px_rgba(8,145,178,0.1)]"
                        >
                            <h3 className="text-2xl font-bold text-white mb-3">{item.title}</h3>
                            <p className="text-gray-400 mb-6">{item.description}</p>
                            <ul className="space-y-3">
                                {item.features.map((feature, fIndex) => (
                                    <li key={fIndex} className="flex items-center text-sm text-gray-300">
                                        <CheckCircle2 className="w-4 h-4 text-cyan-500 mr-2" />
                                        {feature}
                                    </li>
                                ))}
                            </ul>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
