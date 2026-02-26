import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { 
  GraduationCap, 
  Hand, 
  X, 
  Volume2, 
  VolumeX, 
  ArrowLeft,
  Sparkles,
  Mic,
  MicOff
} from "lucide-react";

type SessionState = "teaching" | "listening" | "responding";

const Session = () => {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [fileName, setFileName] = useState("");
  const [sessionState, setSessionState] = useState<SessionState>("teaching");
  const [isMuted, setIsMuted] = useState(false);
  const [currentText, setCurrentText] = useState("");

  // Simulated teaching content
  const teachingContent = [
    "Let me explain this topic to you in a clear and structured way...",
    "The key concept here is understanding how different elements interact with each other.",
    "Think of it like building blocks – each piece connects to form the bigger picture.",
    "Now, let's dive deeper into the specific details you asked about...",
  ];

  useEffect(() => {
    const savedTopic = localStorage.getItem("tutorTopic");
    const savedFileName = localStorage.getItem("tutorFileName");
    
    if (!savedTopic) {
      navigate("/setup");
      return;
    }
    
    setTopic(savedTopic);
    setFileName(savedFileName || "Document");
    
    // Simulate teaching text
    let index = 0;
    const interval = setInterval(() => {
      if (sessionState === "teaching") {
        setCurrentText(teachingContent[index % teachingContent.length]);
        index++;
      }
    }, 4000);

    setCurrentText(teachingContent[0]);

    return () => clearInterval(interval);
  }, [navigate, sessionState]);

  const handleHandRaise = () => {
    if (sessionState === "teaching") {
      setSessionState("listening");
      setCurrentText("I'm listening... Go ahead with your question.");
    } else if (sessionState === "listening") {
      // Simulate getting an answer
      setSessionState("responding");
      setCurrentText("That's a great question! Let me explain...");
      
      // After responding, go back to teaching
      setTimeout(() => {
        setSessionState("teaching");
        setCurrentText("Now, let me continue with where we left off...");
      }, 5000);
    }
  };

  const handleEndSession = () => {
    localStorage.removeItem("tutorTopic");
    localStorage.removeItem("tutorFileName");
    navigate("/");
  };

  const getStateColor = () => {
    switch (sessionState) {
      case "teaching":
        return "border-primary";
      case "listening":
        return "border-accent";
      case "responding":
        return "border-success";
      default:
        return "border-primary";
    }
  };

  const getStateLabel = () => {
    switch (sessionState) {
      case "teaching":
        return { text: "Teaching", color: "text-primary", bgColor: "bg-primary/10" };
      case "listening":
        return { text: "Listening to you", color: "text-accent", bgColor: "bg-accent/10" };
      case "responding":
        return { text: "Responding", color: "text-success", bgColor: "bg-success/10" };
    }
  };

  const stateLabel = getStateLabel();

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm shrink-0">
        <div className="container mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg gradient-hero">
                <GraduationCap className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-bold">TutorAI</span>
            </div>
            
            {/* Session info */}
            <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{fileName}</span>
              <span>•</span>
              <span className="max-w-xs truncate">{topic}</span>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleEndSession}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="w-4 h-4 mr-2" />
              End Session
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-2xl mx-auto flex flex-col items-center gap-8">
          
          {/* Status Badge */}
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${stateLabel.bgColor} ${stateLabel.color}`}>
            {sessionState === "teaching" && <Sparkles className="w-4 h-4" />}
            {sessionState === "listening" && <Mic className="w-4 h-4 animate-pulse" />}
            {sessionState === "responding" && <Volume2 className="w-4 h-4" />}
            <span className="text-sm font-medium">{stateLabel.text}</span>
          </div>

          {/* AI Avatar */}
          <div className={`relative w-48 h-48 md:w-64 md:h-64 rounded-full gradient-avatar border-4 ${getStateColor()} shadow-glow animate-float transition-colors duration-300`}>
            {/* Avatar face - simplified illustration */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="relative">
                {/* Eyes */}
                <div className="flex gap-8 mb-4">
                  <div className="w-4 h-4 md:w-5 md:h-5 rounded-full bg-foreground" />
                  <div className="w-4 h-4 md:w-5 md:h-5 rounded-full bg-foreground" />
                </div>
                {/* Mouth - animated when speaking */}
                <div className={`mx-auto w-12 md:w-16 h-2 rounded-full bg-foreground/80 ${sessionState !== "listening" ? "animate-pulse" : ""}`} />
              </div>
            </div>

            {/* Sound waves when speaking */}
            {sessionState !== "listening" && (
              <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 flex items-end gap-1">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div
                    key={i}
                    className="w-1 bg-primary rounded-full animate-wave"
                    style={{
                      height: `${12 + Math.random() * 12}px`,
                      animationDelay: `${i * 0.1}s`,
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Speech Text */}
          <div className="text-center max-w-xl">
            <p className="text-xl md:text-2xl font-medium leading-relaxed animate-fade-in-up">
              "{currentText}"
            </p>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-4">
            {/* Mute Button */}
            <Button
              variant="outline"
              size="icon"
              onClick={() => setIsMuted(!isMuted)}
              className="rounded-full"
            >
              {isMuted ? (
                <VolumeX className="w-5 h-5" />
              ) : (
                <Volume2 className="w-5 h-5" />
              )}
            </Button>

            {/* Hand Raise Button */}
            <div className="relative">
              {sessionState === "listening" && (
                <>
                  <div className="absolute inset-0 rounded-full bg-accent animate-pulse-ring" />
                  <div className="absolute inset-0 rounded-full bg-accent animate-pulse-ring animation-delay-300" />
                </>
              )}
              <Button
                variant="handRaise"
                size="iconXl"
                onClick={handleHandRaise}
                className={`relative ${sessionState === "listening" ? "bg-accent scale-110" : ""}`}
              >
                {sessionState === "listening" ? (
                  <Mic className="w-8 h-8" />
                ) : (
                  <Hand className="w-8 h-8" />
                )}
              </Button>
            </div>

            {/* Placeholder for symmetry */}
            <div className="w-11 h-11" />
          </div>

          {/* Instruction */}
          <p className="text-sm text-muted-foreground text-center">
            {sessionState === "listening" 
              ? "Speak now... Click again when done"
              : "Raise your hand to ask a question"
            }
          </p>
        </div>
      </main>
    </div>
  );
};

export default Session;
