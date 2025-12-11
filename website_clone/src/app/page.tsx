import { HeroSection } from "@/components/landing/HeroSection";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { TargetAudience } from "@/components/landing/TargetAudience";
import { LocalNodes } from "@/components/landing/LocalNodes";
import { PricingSection } from "@/components/landing/PricingSection";
import { Footer } from "@/components/landing/Footer";
import { NavBar } from "@/components/landing/NavBar";
import { BackgroundParticles } from "@/components/landing/BackgroundParticles";
import { createClient } from "@/lib/supabase/server";

// Landing page теперь дополнительно разлогинивает при заходе, чтобы при выходе с дашборда всегда требовался повторный вход.
export default async function LandingPage() {
  const supabase = await createClient();
  // silent logout on landing visit
  await supabase.auth.signOut();

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
