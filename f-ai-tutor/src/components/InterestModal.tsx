import { useState } from "react";
import { GraduationCap, Mail, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const CONTACT_EMAIL = "adityaraj61522@gmail.com";

interface InterestModalProps {
    /** "session" = already used this browser session; "ip" = IP rate-limited by server */
    reason?: "session" | "ip";
}

const InterestModal = ({ reason = "session" }: InterestModalProps) => {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [message, setMessage] = useState("");

    const handleShowInterest = () => {
        const subject = encodeURIComponent(`Interest in TutorAI – ${name || "Anonymous"}`);
        const body = encodeURIComponent(
            [
                `Hi Aditya,`,
                ``,
                `I am interested in getting full access to TutorAI.`,
                ``,
                `Name    : ${name || "Not provided"}`,
                `Email   : ${email || "Not provided"}`,
                `Message : ${message || "No message"}`,
                ``,
                `Date    : ${new Date().toUTCString()}`,
                `Reason  : ${reason === "ip" ? "IP rate-limited" : "Session already used"}`,
            ].join("\n")
        );

        window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
    };

    const isFormValid = name.trim().length > 0 && email.trim().includes("@");

    return (
        /* Full-screen non-dismissible overlay */
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
            <div className="mx-4 w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl">
                {/* Header */}
                <div className="flex flex-col items-center gap-3 px-8 pt-8 pb-4 text-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
                        <Lock className="h-7 w-7 text-destructive" />
                    </div>
                    <h2 className="text-2xl font-bold">Session Limit Reached</h2>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                        {reason === "ip"
                            ? "You've already used your free TutorAI session."
                            : "You've already used your free TutorAI session."}
                        {" "}Show your interest below and we'll get back to you with full access.
                    </p>
                </div>

                {/* Divider */}
                <div className="h-px bg-border mx-6" />

                {/* Interest form */}
                <div className="space-y-4 px-8 py-6">
                    <div className="space-y-1.5">
                        <Label htmlFor="interest-name">Your Name <span className="text-destructive">*</span></Label>
                        <Input
                            id="interest-name"
                            placeholder="Jane Doe"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>

                    <div className="space-y-1.5">
                        <Label htmlFor="interest-email">Your Email <span className="text-destructive">*</span></Label>
                        <Input
                            id="interest-email"
                            type="email"
                            placeholder="jane@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>

                    <div className="space-y-1.5">
                        <Label htmlFor="interest-msg">What would you like to learn? <span className="text-muted-foreground text-xs">(optional)</span></Label>
                        <Textarea
                            id="interest-msg"
                            placeholder="e.g., Machine learning fundamentals, Quantum physics…"
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            className="min-h-[80px] resize-none"
                        />
                    </div>

                    <Button
                        onClick={handleShowInterest}
                        disabled={!isFormValid}
                        className="w-full gap-2"
                        size="lg"
                    >
                        <Mail className="h-4 w-4" />
                        Show Interest
                    </Button>
                </div>

                {/* Footer branding */}
                <div className="flex items-center justify-center gap-2 rounded-b-2xl bg-muted/30 px-8 py-4 border-t border-border">
                    <div className="p-1.5 rounded-md gradient-hero">
                        <GraduationCap className="h-4 w-4 text-primary-foreground" />
                    </div>
                    <span className="text-sm font-semibold text-muted-foreground">TutorAI</span>
                </div>
            </div>
        </div>
    );
};

export default InterestModal;
