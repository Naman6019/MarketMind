"use client";

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowRight, BarChart3, LineChart, Cpu, ShieldCheck, Zap } from 'lucide-react';

export default function LandingPage() {
  const fadeIn = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };

  const staggerContainer = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2
      }
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#0b0c10] text-[#c5c6c7] font-sans selection:bg-[#66fcf1] selection:text-[#0b0c10]">
      {/* Background Glows */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-[#45a29e] opacity-[0.15] blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-[#66fcf1] opacity-[0.1] blur-[120px]" />
      </div>

      {/* Navigation */}
      <nav className="flex items-center justify-between px-6 py-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#66fcf1] to-[#45a29e] shadow-[0_0_20px_rgba(102,252,241,0.4)] flex items-center justify-center">
            <LineChart className="text-[#0b0c10] w-6 h-6" />
          </div>
          <span className="text-xl font-bold text-white tracking-wide">MarketMind</span>
        </div>
        <Link 
          href="/dashboard"
          className="px-6 py-2.5 rounded-full bg-[rgba(31,40,51,0.8)] border border-[rgba(197,198,199,0.1)] text-white font-medium hover:bg-[#1f2833] hover:border-[#66fcf1] transition-all duration-300 flex items-center gap-2 group shadow-[0_4px_20px_rgba(0,0,0,0.3)] backdrop-blur-md"
        >
          Launch App
          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </Link>
      </nav>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-6 pt-20 pb-32">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <motion.div 
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
            className="flex flex-col gap-8"
          >
            <motion.div variants={fadeIn} className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[rgba(102,252,241,0.1)] border border-[rgba(102,252,241,0.2)] w-fit">
              <Zap className="w-4 h-4 text-[#66fcf1]" />
              <span className="text-sm font-medium text-[#66fcf1]">AI-Orchestrated Financial Research</span>
            </motion.div>
            
            <motion.h1 variants={fadeIn} className="text-5xl lg:text-7xl font-bold text-white leading-tight">
              Smarter Markets.<br/>
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#66fcf1] to-[#45a29e]">
                Sharper Minds.
              </span>
            </motion.h1>
            
            <motion.p variants={fadeIn} className="text-lg text-[#8a9199] max-w-xl leading-relaxed">
              MarketMind fuses real-time quantitative metrics with AI-driven news sentiment to provide retail investors with institutional-grade insights for the Indian stock and mutual fund markets.
            </motion.p>
            
            <motion.div variants={fadeIn} className="flex flex-col sm:flex-row gap-4 pt-4">
              <Link 
                href="/dashboard"
                className="px-8 py-4 rounded-xl bg-gradient-to-r from-[#66fcf1] to-[#45a29e] text-[#0b0c10] font-bold text-lg hover:shadow-[0_0_30px_rgba(102,252,241,0.5)] transition-all duration-300 flex items-center justify-center gap-2"
              >
                Start Researching Now
                <ArrowRight className="w-5 h-5" />
              </Link>
              <a 
                href="#features"
                className="px-8 py-4 rounded-xl bg-[rgba(31,40,51,0.6)] border border-[rgba(197,198,199,0.1)] text-white font-medium hover:bg-[#1f2833] transition-all duration-300 flex items-center justify-center backdrop-blur-md"
              >
                Explore Features
              </a>
            </motion.div>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, scale: 0.9, rotateX: 10 }}
            animate={{ opacity: 1, scale: 1, rotateX: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="relative perspective-1000"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-[#66fcf1]/20 to-transparent rounded-2xl blur-2xl transform -rotate-3" />
            <div className="relative rounded-2xl border border-[rgba(197,198,199,0.1)] bg-[#1f2833]/80 backdrop-blur-xl p-2 shadow-2xl overflow-hidden transform hover:scale-[1.02] transition-transform duration-500">
              <Image 
                src="/hero.png" 
                alt="MarketMind Dashboard Preview" 
                width={800} 
                height={600} 
                className="rounded-xl w-full h-auto border border-[rgba(255,255,255,0.05)]"
                priority
              />
            </div>
          </motion.div>
        </div>
      </main>

      {/* Features Section */}
      <section id="features" className="py-32 relative bg-[rgba(11,12,16,0.8)] border-y border-[rgba(197,198,199,0.05)]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-5xl font-bold text-white mb-6">Built for the Modern Investor</h2>
            <p className="text-[#8a9199] text-lg max-w-2xl mx-auto">Everything you need to analyze, compare, and understand the markets without the noise.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: <Cpu className="w-8 h-8 text-[#66fcf1]" />,
                title: "Multi-Agent AI Pipeline",
                desc: "An intelligent router classifies your intent, dispatching dedicated agents for quant data fetching and news sentiment analysis."
              },
              {
                icon: <BarChart3 className="w-8 h-8 text-[#66fcf1]" />,
                title: "Deep Quant Analytics",
                desc: "Real-time auto-computed metrics including Alpha, Beta, Sharpe Ratio, and CAGR directly overlaid on historic NAV charts."
              },
              {
                icon: <ShieldCheck className="w-8 h-8 text-[#66fcf1]" />,
                title: "Head-to-Head Comparisons",
                desc: "Compare mutual funds side-by-side with normalized performance charts and sector concentration breakdowns."
              }
            ].map((feature, idx) => (
              <motion.div 
                key={idx}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.2 }}
                className="bg-[#1f2833]/40 border border-[rgba(197,198,199,0.1)] p-8 rounded-2xl hover:bg-[#1f2833]/80 transition-colors backdrop-blur-sm group"
              >
                <div className="w-16 h-16 rounded-2xl bg-[rgba(102,252,241,0.05)] flex items-center justify-center mb-6 border border-[rgba(102,252,241,0.1)] group-hover:scale-110 transition-transform">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold text-white mb-4">{feature.title}</h3>
                <p className="text-[#8a9199] leading-relaxed">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-[rgba(197,198,199,0.05)] text-center">
        <div className="flex items-center justify-center gap-2 mb-6">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-[#66fcf1] to-[#45a29e] flex items-center justify-center">
            <LineChart className="text-[#0b0c10] w-3 h-3" />
          </div>
          <span className="text-lg font-bold text-white">MarketMind</span>
        </div>
        <p className="text-[#8a9199] text-sm">
          &copy; {new Date().getFullYear()} MarketMind. All rights reserved. <br/>
          Built with Next.js & FastAPI.
        </p>
      </footer>
    </div>
  );
}
