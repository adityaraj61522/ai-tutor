import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  GraduationCap,
  Hand,
  X,
  Volume2,
  VolumeX,
  Sparkles,
  Mic,
  MicOff,
  Send,
  Loader2,
} from "lucide-react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL as string;
const EMPTY_QUEUE_RETRY_MS = 2500;
const ERROR_RETRY_MS = 4000;
const MAX_QUESTION_LEN = 500; // mirrors server truncation limit

type SessionState = "teaching" | "listening" | "responding";

// ---------------------------------------------------------------------------
// Web Speech typings (not in lib.dom.d.ts in older TS targets)
// ---------------------------------------------------------------------------
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
}
declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  }
  interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start(): void;
    stop(): void;
    onresult: ((e: SpeechRecognitionEvent) => void) | null;
    onend: (() => void) | null;
    onerror: ((e: Event) => void) | null;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const Session = () => {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [fileName, setFileName] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [sessionState, setSessionState] = useState<SessionState>("teaching");
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [currentText, setCurrentText] = useState("Preparing your learning session…");

  // Question input (typed or speech-recognised)
  const [questionText, setQuestionText] = useState("");
  const [isSubmittingQuestion, setIsSubmittingQuestion] = useState(false);
  const [isRecognising, setIsRecognising] = useState(false);
  const [questionLimitReached, setQuestionLimitReached] = useState(false);
  const [questionRateLimited, setQuestionRateLimited] = useState(false);

  // Refs kept stable across renders
  const sessionStateRef = useRef<SessionState>("teaching");
  const isMutedRef = useRef(false);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  // True once the server returns done:true — prevents the loop from spinning
  // on an empty queue. Reset to false each time a question is submitted so
  // polling resumes when the answer sentences are pushed.
  const teachingIdleRef = useRef(false);
  // AbortController for the current in-flight /next fetch; cancelled on
  // unmount and whenever we deliberately stop the loop.
  const fetchAbortRef = useRef<AbortController | null>(null);

  // Keep refs in sync with state
  useEffect(() => { sessionStateRef.current = sessionState; }, [sessionState]);
  useEffect(() => { isMutedRef.current = isMuted; }, [isMuted]);

  // ---------------------------------------------------------------------------
  // TTS
  // ---------------------------------------------------------------------------

  const speakSentence = useCallback(
    (text: string, onFinished: () => void) => {
      if (isMutedRef.current) {
        setCurrentText(text);
        setIsSpeaking(false);
        onFinished();
        return;
      }

      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.92;
      utterance.pitch = 1.05;

      utterance.onstart = () => {
        setCurrentText(text);
        setIsSpeaking(true);
      };
      utterance.onend = () => {
        setIsSpeaking(false);
        onFinished();
      };
      utterance.onerror = () => {
        setIsSpeaking(false);
        onFinished();
      };

      window.speechSynthesis.speak(utterance);
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Polling loop — declared with useCallback so it can reference itself
  // ---------------------------------------------------------------------------

  const pollNext = useCallback(
    (sid: string) => {
      if (sessionStateRef.current === "listening") return;

      // Cancel any previous in-flight request before starting a new one
      fetchAbortRef.current?.abort();
      const controller = new AbortController();
      fetchAbortRef.current = controller;

      fetch(`${BACKEND_URL}/session/${sid}/next`, { signal: controller.signal })
        .then((r) => r.json())
        .then((data) => {
          if (data.text) {
            // Got a sentence — speak it, then immediately poll for the next
            speakSentence(data.text, () => {
              if (sessionStateRef.current !== "listening") {
                pollTimeoutRef.current = setTimeout(
                  () => pollNext(sid),
                  300,
                );
              }
            });
          } else if (data.done) {
            // Server confirmed the queue is fully drained — stop the loop.
            // Polling will be restarted explicitly when a question is submitted.
            teachingIdleRef.current = true;
            setSessionState("teaching");
            setCurrentText("All caught up! Raise your hand to ask a question.");
            setIsSpeaking(false);
          } else {
            // Transient empty queue (e.g. question still being processed) — retry
            pollTimeoutRef.current = setTimeout(
              () => pollNext(sid),
              EMPTY_QUEUE_RETRY_MS,
            );
          }
        })
        .catch((err: unknown) => {
          // AbortError means we deliberately cancelled — don't retry
          if (err instanceof Error && err.name === "AbortError") return;
          pollTimeoutRef.current = setTimeout(
            () => pollNext(sid),
            ERROR_RETRY_MS,
          );
        });
    },
    [speakSentence],
  );

  // ---------------------------------------------------------------------------
  // Bootstrap on mount
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const sid = localStorage.getItem("tutorSessionId");
    const savedTopic = localStorage.getItem("tutorTopic");
    const savedFileName = localStorage.getItem("tutorFileName");

    if (!sid || !savedTopic) {
      navigate("/setup");
      return;
    }

    setSessionId(sid);
    setTopic(savedTopic);
    setFileName(savedFileName || "Document");

    // Short delay so state is committed before polling starts
    pollTimeoutRef.current = setTimeout(() => pollNext(sid), 500);

    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
      fetchAbortRef.current?.abort();
      window.speechSynthesis.cancel();
      recognitionRef.current?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-start polling when mute is turned OFF while not listening
  useEffect(() => {
    // Only kick the loop if teaching still has content (not idled after done:true)
    if (!isMuted && !isSpeaking && sessionState !== "listening" && sessionId && !teachingIdleRef.current) {
      // If we turned mute off, kick the loop (it may have stalled)
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = setTimeout(() => pollNext(sessionId), 300);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMuted]);

  // ---------------------------------------------------------------------------
  // Hand raise / question handling
  // ---------------------------------------------------------------------------

  const handleHandRaise = () => {
    if (sessionState === "teaching" || sessionState === "responding") {
      // Pause speech and enter listening mode
      window.speechSynthesis.cancel();
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
      fetchAbortRef.current?.abort();
      setIsSpeaking(false);
      setSessionState("listening");
      setCurrentText("I'm listening… Go ahead with your question.");
      startSpeechRecognition();
    } else if (sessionState === "listening") {
      // Cancel listening and go back to teaching
      recognitionRef.current?.stop();
      setIsRecognising(false);
      setSessionState("teaching");
      // Only restart polling if the initial lesson wasn't already exhausted
      if (sessionId && !teachingIdleRef.current) {
        pollTimeoutRef.current = setTimeout(() => pollNext(sessionId), 300);
      }
    }
  };

  const startSpeechRecognition = () => {
    const SR =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return; // Fallback: user types in the textarea

    const recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      const transcript = e.results[0]?.[0]?.transcript ?? "";
      setQuestionText((prev) => prev + (prev ? " " : "") + transcript);
    };
    recognition.onend = () => setIsRecognising(false);
    recognition.onerror = () => setIsRecognising(false);

    recognitionRef.current = recognition;
    setIsRecognising(true);
    recognition.start();
  };

  const handleSubmitQuestion = async () => {
    if (!questionText.trim() || !sessionId || isSubmittingQuestion) return;

    recognitionRef.current?.stop();
    setIsRecognising(false);
    setIsSubmittingQuestion(true);
    setSessionState("responding");
    setCurrentText("Great question! Let me think about that…");

    // Reset the idle flag so the polling loop will run again once the
    // answer sentences are pushed to the queue by the server.
    teachingIdleRef.current = false;

    try {
      const res = await fetch(
        `${BACKEND_URL}/session/${sessionId}/question`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: questionText }),
        },
      );

      if (res.status === 429) {
        const body = await res.json().catch(() => ({}));
        if (body.error === "question_limit_reached") {
          setQuestionLimitReached(true);
          setSessionState("teaching");
          setCurrentText("You've reached the question limit for this session. Let's continue with the lesson!");
        } else {
          // Per-30s rate limit hit
          setQuestionRateLimited(true);
          setSessionState("teaching");
          setCurrentText("Please wait 30 seconds before asking another question.");
          setTimeout(() => setQuestionRateLimited(false), 30_000);
        }
        if (sessionId) {
          pollTimeoutRef.current = setTimeout(() => pollNext(sessionId), 3000);
        }
        return;
      }

      if (!res.ok) throw new Error("Failed to submit question");

      setQuestionText("");
      // Start polling the answer sentences
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = setTimeout(() => pollNext(sessionId), 500);
    } catch {
      setSessionState("teaching");
      setCurrentText("Sorry, I had trouble answering that. Let's continue…");
      if (sessionId) {
        pollTimeoutRef.current = setTimeout(() => pollNext(sessionId), 2000);
      }
    } finally {
      setIsSubmittingQuestion(false);
    }
  };

  const handleEndSession = () => {
    window.speechSynthesis.cancel();
    recognitionRef.current?.stop();
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    fetchAbortRef.current?.abort();
    localStorage.removeItem("tutorSessionId");
    localStorage.removeItem("tutorTopic");
    localStorage.removeItem("tutorFileName");
    navigate("/");
  };

  // ---------------------------------------------------------------------------
  // UI helpers
  // ---------------------------------------------------------------------------

  const getStateColor = () => {
    switch (sessionState) {
      case "teaching": return "border-primary";
      case "listening": return "border-accent";
      case "responding": return "border-success";
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

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

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
          <div
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${stateLabel.bgColor} ${stateLabel.color}`}
          >
            {sessionState === "teaching" && <Sparkles className="w-4 h-4" />}
            {sessionState === "listening" && (
              <Mic className="w-4 h-4 animate-pulse" />
            )}
            {sessionState === "responding" && <Volume2 className="w-4 h-4" />}
            <span className="text-sm font-medium">{stateLabel.text}</span>
          </div>

          {/* AI Avatar */}
          <div
            className={`relative w-48 h-48 md:w-64 md:h-64 rounded-full gradient-avatar border-4 ${getStateColor()} shadow-glow animate-float transition-colors duration-300`}
          >
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="relative">
                {/* Eyes */}
                <div className="flex gap-8 mb-4">
                  <div className="w-4 h-4 md:w-5 md:h-5 rounded-full bg-foreground" />
                  <div className="w-4 h-4 md:w-5 md:h-5 rounded-full bg-foreground" />
                </div>
                {/* Mouth — animated while speaking */}
                <div
                  className={`mx-auto w-12 md:w-16 h-2 rounded-full bg-foreground/80 ${isSpeaking ? "animate-pulse" : ""}`}
                />
              </div>
            </div>

            {/* Sound waves while speaking */}
            {isSpeaking && (
              <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 flex items-end gap-1">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div
                    key={i}
                    className="w-1 bg-primary rounded-full animate-wave"
                    style={{
                      height: `${12 + (i % 3) * 6}px`,
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

          {/* Question panel — shown while listening */}
          {sessionState === "listening" && (
            <div className="w-full space-y-3 animate-fade-in-up">
              {questionLimitReached && (
                <div className="px-4 py-3 rounded-xl bg-destructive/10 border border-destructive/30 text-destructive text-sm text-center">
                  You’ve used all 20 questions for this session.
                </div>
              )}
              {questionRateLimited && (
                <div className="px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-sm text-center">
                  Slow down a little — you're asking questions very quickly. Please wait 30 seconds.
                </div>
              )}
              <div className="relative">
                <Textarea
                  placeholder={
                    isRecognising
                      ? "Listening… speak your question"
                      : "Type your question here…"
                  }
                  value={questionText}
                  maxLength={MAX_QUESTION_LEN}
                  onChange={(e) => setQuestionText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmitQuestion();
                    }
                  }}
                  disabled={questionLimitReached}
                  className="resize-none min-h-[80px] text-base pr-16"
                />
                <span className={`absolute bottom-2 right-3 text-xs tabular-nums pointer-events-none ${questionText.length >= MAX_QUESTION_LEN - 50
                  ? "text-destructive font-medium"
                  : "text-muted-foreground"
                  }`}>
                  {questionText.length}/{MAX_QUESTION_LEN}
                </span>
              </div>
              <div className="flex gap-3">
                {(window.SpeechRecognition || window.webkitSpeechRecognition) && (
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => {
                      if (isRecognising) {
                        recognitionRef.current?.stop();
                        setIsRecognising(false);
                      } else {
                        startSpeechRecognition();
                      }
                    }}
                    disabled={questionLimitReached}
                    className={`rounded-full ${isRecognising ? "text-destructive border-destructive" : ""}`}
                    title={isRecognising ? "Stop recording" : "Start voice input"}
                  >
                    {isRecognising ? (
                      <MicOff className="w-5 h-5" />
                    ) : (
                      <Mic className="w-5 h-5" />
                    )}
                  </Button>
                )}
                <Button
                  variant="hero"
                  className="flex-1 gap-2"
                  onClick={handleSubmitQuestion}
                  disabled={!questionText.trim() || isSubmittingQuestion || questionLimitReached || questionRateLimited}
                >
                  {isSubmittingQuestion ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                  Ask
                </Button>
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="flex items-center gap-4">
            {/* Mute / unmute */}
            <Button
              variant="outline"
              size="icon"
              onClick={() => setIsMuted(!isMuted)}
              className="rounded-full"
              title={isMuted ? "Unmute" : "Mute"}
            >
              {isMuted ? (
                <VolumeX className="w-5 h-5" />
              ) : (
                <Volume2 className="w-5 h-5" />
              )}
            </Button>

            {/* Hand raise */}
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
                disabled={questionLimitReached && sessionState !== "listening"}
                className={`relative ${sessionState === "listening" ? "bg-accent scale-110" : ""}`}
                title={
                  questionLimitReached
                    ? "Question limit reached for this session"
                    : sessionState === "listening"
                      ? "Cancel — go back to teaching"
                      : "Raise hand to ask a question"
                }
              >
                {sessionState === "listening" ? (
                  <Hand className="w-8 h-8" />
                ) : (
                  <Hand className="w-8 h-8" />
                )}
              </Button>
            </div>

            {/* Spacer */}
            <div className="w-11 h-11" />
          </div>

          {/* Instruction */}
          <p className="text-sm text-muted-foreground text-center">
            {questionLimitReached
              ? "You’ve used all your questions for this session."
              : questionRateLimited
                ? "Too many questions in a short time — please wait 30 seconds."
                : sessionState === "listening"
                  ? "Type or speak your question, then click Ask"
                  : "Raise your hand to pause and ask a question"}
          </p>
        </div>
      </main>
    </div>
  );
};

export default Session;
