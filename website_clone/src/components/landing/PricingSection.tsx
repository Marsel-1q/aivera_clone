"use client";

import { motion } from "framer-motion";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const plans = [
    {
        name: "Starter",
        price: "Free",
        description: "Попробуйте создать своего первого клона и пообщаться с ним.",
        features: [
            "1 AI Клон",
            "Базовая модель (Llama 3 8B)",
            "Ограничение 50 сообщений/день",
            "Веб-интерфейс",
        ],
        highlight: false,
        buttonText: "Попробовать бесплатно",
    },
    {
        name: "Pro",
        price: "$29",
        period: "/ месяц",
        description: "Для креаторов и профессионалов, желающих высокого качества.",
        features: [
            "3 AI Клона",
            "Продвинутая модель (Qwen 2.5 32B)",
            "Безлимитные сообщения",
            "Telegram интеграция",
            "Приоритетная очередь обучения",
        ],
        highlight: true,
        buttonText: "Начать с Pro",
    },
    {
        name: "Business",
        price: "$99",
        period: "/ месяц",
        description: "Для компаний: локальный деплой, API и командный доступ.",
        features: [
            "10+ Клонов",
            "Все доступные модели",
            "API Доступ",
            "Выгрузка локальной ноды",
            "Удаление копирайта",
            "Командный доступ",
        ],
        highlight: false,
        buttonText: "Связаться с нами",
    },
];

export function PricingSection() {
    return (
        <section className="py-24 px-4 relative z-10">
            <div className="container mx-auto max-w-6xl">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center mb-16"
                >
                    <h2 className="text-3xl md:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400 mb-4">
                        Прозрачные тарифы
                    </h2>
                    <p className="text-gray-400 text-lg">
                        Начните бесплатно, платите по мере роста.
                    </p>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {plans.map((plan, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 30 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className={`relative flex flex-col p-8 rounded-2xl border ${plan.highlight
                                ? "border-cyan-500/50 bg-cyan-950/10 shadow-[0_0_40px_rgba(8,145,178,0.1)]"
                                : "border-white/10 bg-white/5"
                                }`}
                        >
                            {plan.highlight && (
                                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-cyan-500 text-black text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide">
                                    Most Popular
                                </div>
                            )}

                            <div className="mb-8">
                                <h3 className="text-xl font-medium text-white mb-2">{plan.name}</h3>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-4xl font-bold text-white">{plan.price}</span>
                                    {plan.period && <span className="text-gray-400">{plan.period}</span>}
                                </div>
                                <p className="text-gray-400 text-sm mt-4">{plan.description}</p>
                            </div>

                            <ul className="space-y-4 mb-8 flex-1">
                                {plan.features.map((feature, i) => (
                                    <li key={i} className="flex items-start text-sm text-gray-300">
                                        <Check className="w-4 h-4 text-cyan-500 mr-3 mt-0.5 shrink-0" />
                                        {feature}
                                    </li>
                                ))}
                            </ul>

                            <Button
                                variant={plan.highlight ? "default" : "outline"}
                                className={`w-full ${plan.highlight
                                    ? "bg-cyan-600 hover:bg-cyan-500 text-white border-0"
                                    : "border-white/20 text-white hover:bg-white/10 hover:text-white"
                                    }`}
                            >
                                {plan.buttonText}
                            </Button>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
