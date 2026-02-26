import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles, BookOpen, Mic } from "lucide-react";
import { useNavigate } from "react-router-dom";

export const Hero = () => {
  const navigate = useNavigate();

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-20 left-10 w-72 h-72 bg-primary/10 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-accent/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-secondary/50 rounded-full blur-3xl" />
      </div>

      <div className="container mx-auto px-6 py-20">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-secondary text-secondary-foreground text-sm font-medium mb-8 animate-fade-in-up">
            <Sparkles className="w-4 h-4 text-accent" />
            <span>AI-Powered Learning Experience</span>
          </div>

          {/* Headline */}
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-extrabold leading-tight mb-6 animate-fade-in-up animation-delay-100">
            Learn Anything with Your
            <span className="text-primary block mt-2">Personal AI Tutor</span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl md:text-2xl text-muted-foreground max-w-2xl mx-auto mb-10 animate-fade-in-up animation-delay-200">
            Upload any document, choose your topic, and let your AI tutor guide you through interactive voice-based learning sessions.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-up animation-delay-300">
            <Button
              variant="hero"
              size="xl"
              onClick={() => navigate("/setup")}
              className="group"
            >
              Get Started
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button variant="outline" size="lg">
              Watch Demo
            </Button>
          </div>

          {/* Feature pills */}
          <div className="flex flex-wrap items-center justify-center gap-4 mt-16 animate-fade-in-up animation-delay-400">
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-card shadow-card">
              <BookOpen className="w-5 h-5 text-primary" />
              <span className="text-sm font-medium">Upload Documents</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-card shadow-card">
              <Sparkles className="w-5 h-5 text-accent" />
              <span className="text-sm font-medium">AI Avatar Teaching</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-card shadow-card">
              <Mic className="w-5 h-5 text-success" />
              <span className="text-sm font-medium">Voice Interaction</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
