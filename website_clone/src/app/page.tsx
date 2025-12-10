import { HeroSection } from "@/components/landing/HeroSection";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { TargetAudience } from "@/components/landing/TargetAudience";
import { LocalNodes } from "@/components/landing/LocalNodes";
import { PricingSection } from "@/components/landing/PricingSection";
import { Footer } from "@/components/landing/Footer";
import { NavBar } from "@/components/landing/NavBar";

import { BackgroundParticles } from "@/components/landing/BackgroundParticles";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-black text-white selection:bg-cyan-500/30 relative">
      <NavBar />
      <BackgroundParticles />
      <HeroSection />
      <HowItWorks />
      <TargetAudience />
      <LocalNodes />
      <PricingSection />
      <Footer />
    </main>
  );
}
