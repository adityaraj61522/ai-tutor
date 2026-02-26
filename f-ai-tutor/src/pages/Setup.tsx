import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { GraduationCap, Upload, FileText, X, ArrowRight, ArrowLeft } from "lucide-react";

const Setup = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [topic, setTopic] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
    }
  };

  const removeFile = () => {
    setFile(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Store the setup data and navigate to session
    if (file && topic.trim()) {
      // In a real app, you'd upload the file and process it
      localStorage.setItem("tutorTopic", topic);
      localStorage.setItem("tutorFileName", file.name);
      navigate("/session");
    }
  };

  const isValid = file && topic.trim().length > 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            <button
              onClick={() => navigate("/")}
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg gradient-hero">
                <GraduationCap className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-bold">TutorAI</span>
            </div>
            <div className="w-16" /> {/* Spacer for centering */}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-12">
        <div className="max-w-2xl mx-auto">
          {/* Title */}
          <div className="text-center mb-10">
            <h1 className="text-3xl md:text-4xl font-bold mb-3">
              Set Up Your <span className="text-gradient">Learning Session</span>
            </h1>
            <p className="text-lg text-muted-foreground">
              Upload your study material and tell us what you'd like to learn.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* File Upload */}
            <div className="space-y-3">
              <Label className="text-base font-semibold">Upload Document</Label>
              
              {!file ? (
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-200 ${
                    isDragging
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50 hover:bg-muted/30"
                  }`}
                >
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx,.txt,.md"
                    onChange={handleFileChange}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <div className="flex flex-col items-center gap-4">
                    <div className="p-4 rounded-full bg-primary/10">
                      <Upload className="w-8 h-8 text-primary" />
                    </div>
                    <div>
                      <p className="text-lg font-medium mb-1">
                        Drop your file here or <span className="text-primary">browse</span>
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Supports PDF, DOC, DOCX, TXT, MD
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-4 p-4 rounded-xl bg-secondary border border-border">
                  <div className="p-3 rounded-lg bg-primary/10">
                    <FileText className="w-6 h-6 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{file.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={removeFile}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <X className="w-5 h-5" />
                  </Button>
                </div>
              )}
            </div>

            {/* Topic Input */}
            <div className="space-y-3">
              <Label htmlFor="topic" className="text-base font-semibold">
                What would you like to learn?
              </Label>
              <Textarea
                id="topic"
                placeholder="e.g., Explain the key concepts of photosynthesis from chapter 3..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="min-h-[120px] resize-none text-base"
              />
              <p className="text-sm text-muted-foreground">
                Be specific about the topic or concept you want to understand.
              </p>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="hero"
              size="xl"
              className="w-full group"
              disabled={!isValid}
            >
              Start Learning Session
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default Setup;
