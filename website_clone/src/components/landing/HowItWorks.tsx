"use client";

import { motion } from "framer-motion";
import { MessageSquareText, Settings2, Rocket } from "lucide-react";

const steps = [
    {
        icon: <MessageSquareText className="w-10 h-10 text-cyan-400" />,
        title: "1. Загрузи диалоги",
        description: "Экспортируй чаты из Telegram, WhatsApp или загрузи файлы. Наша система автоматически очистит и структурирует данные.",
        color: "from-cyan-500/20 to-blue-500/5",
    },
    {
        icon: <Settings2 className="w-10 h-10 text-purple-400" />,
        title: "2. Настрой поведение",
        description: "Определи стиль общения с помощью слайдеров. Задай границы, табу-темы и уровень эмоциональности твоего клона.",
        color: "from-purple-500/20 to-pink-500/5",
    },
    {
        icon: <Rocket className="w-10 h-10 text-indigo-400" />,
        title: "3. Разверни клона",
        description: "Общайся с клоном в Telegram, подключи к WhatsApp или выгрузи модель для запуска на собственном сервере.",
        color: "from-indigo-500/20 to-violet-500/5",
    },
];

export function HowItWorks() {
    return (
        <section className="py-24 relative overflow-hidden z-10">
            <div className="container mx-auto px-4 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-16"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                        Как это работает?
                    </h2>
                    <p className="text-gray-400 text-lg max-w-2xl mx-auto">
                        Три простых шага от истории переписки до полноценного цифрового двойника.
                    </p>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {steps.map((step, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 30 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.2, duration: 0.6 }}
                            className={`p-1 rounded-2xl bg-gradient-to-br ${step.color} border border-white/5 hover:border-white/10 transition-all group`}
                        >
                            <div className="bg-black/80 backdrop-blur-sm p-8 rounded-xl h-full flex flex-col items-center text-center hover:bg-black/60 transition-colors">
                                <div className="mb-6 p-4 rounded-full bg-white/5 group-hover:bg-white/10 transition-colors group-hover:scale-110 duration-300">
                                    {step.icon}
                                </div>
                                <h3 className="text-xl font-bold text-white mb-4">{step.title}</h3>
                                <p className="text-gray-400 leading-relaxed">{step.description}</p>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
