"use client";

import Link from "next/link";
import { Github, Twitter, Linkedin } from "lucide-react";

export function Footer() {
    return (
        <footer className="bg-black border-t border-white/10 pt-16 pb-8 relative z-10">
            <div className="container mx-auto px-4">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
                    <div className="col-span-1 md:col-span-1">
                        <Link href="/" className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-500 mb-4 inline-block">
                            Aivera
                        </Link>
                        <p className="text-gray-500 text-sm leading-relaxed">
                            Платформа для создания реалистичных цифровых двойников. Обучайте, настраивайте и деплойте своих персональных AI-агентов.
                        </p>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-4">Продукт</h4>
                        <ul className="space-y-2 text-sm text-gray-500">
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Возможности</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Интеграции</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Безопасность</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Roadmap</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-4">Ресурсы</h4>
                        <ul className="space-y-2 text-sm text-gray-500">
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Документация</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">API Reference</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Блог</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Сообщество</Link></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-4">Компания</h4>
                        <ul className="space-y-2 text-sm text-gray-500">
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">О нас</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Карьера</Link></li>
                            <li><Link href="#" className="hover:text-cyan-400 transition-colors">Контакты</Link></li>
                        </ul>
                    </div>
                </div>

                <div className="border-t border-white/5 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
                    <p className="text-gray-600 text-sm">
                        © 2025 Aivera Inc. All rights reserved.
                    </p>
                    <div className="flex gap-4">
                        <Link href="#" className="text-gray-500 hover:text-white transition-colors"><Twitter className="w-5 h-5" /></Link>
                        <Link href="#" className="text-gray-500 hover:text-white transition-colors"><Github className="w-5 h-5" /></Link>
                        <Link href="#" className="text-gray-500 hover:text-white transition-colors"><Linkedin className="w-5 h-5" /></Link>
                    </div>
                </div>
            </div>
        </footer>
    );
}
