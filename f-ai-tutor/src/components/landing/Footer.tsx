import { GraduationCap } from "lucide-react";

export const Footer = () => {
  return (
    <footer className="py-12 bg-muted/30 border-t border-border">
      <div className="container mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg gradient-hero">
              <GraduationCap className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold">TutorAI</span>
          </div>

          {/* Copyright */}
          <p className="text-sm text-muted-foreground">
            © 2025 TutorAI. Making learning personal.
          </p>
        </div>
      </div>
    </footer>
  );
};
