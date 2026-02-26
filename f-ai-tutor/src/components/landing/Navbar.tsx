import { Button } from "@/components/ui/button";
import { GraduationCap } from "lucide-react";
import { useNavigate } from "react-router-dom";

export const Navbar = () => {
  const navigate = useNavigate();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border/50">
      <div className="container mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg gradient-hero">
              <GraduationCap className="w-6 h-6 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold">TutorAI</span>
          </div>

          {/* CTA */}
          <Button
            variant="default"
            onClick={() => navigate("/setup")}
          >
            Get Started
          </Button>
        </div>
      </div>
    </nav>
  );
};
