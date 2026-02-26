import { Upload, Sparkles, MessageCircle, Brain, Target, Zap } from "lucide-react";

const features = [
  {
    icon: Upload,
    title: "Upload Any Document",
    description: "PDFs, notes, textbooks – your AI tutor learns from your materials instantly.",
    color: "text-primary",
    bgColor: "bg-primary/10",
  },
  {
    icon: Sparkles,
    title: "Interactive AI Avatar",
    description: "A friendly AI tutor explains concepts with clear, engaging explanations.",
    color: "text-accent",
    bgColor: "bg-accent/10",
  },
  {
    icon: MessageCircle,
    title: "Voice Interaction",
    description: "Raise your hand anytime to ask questions using natural voice conversation.",
    color: "text-success",
    bgColor: "bg-success/10",
  },
  {
    icon: Brain,
    title: "Adaptive Learning",
    description: "The tutor adapts to your pace and understanding level automatically.",
    color: "text-primary",
    bgColor: "bg-primary/10",
  },
  {
    icon: Target,
    title: "Focused Sessions",
    description: "Learn specific topics with structured, goal-oriented tutoring sessions.",
    color: "text-accent",
    bgColor: "bg-accent/10",
  },
  {
    icon: Zap,
    title: "Instant Answers",
    description: "Get immediate responses to your questions without waiting.",
    color: "text-success",
    bgColor: "bg-success/10",
  },
];

export const Features = () => {
  return (
    <section className="py-24 bg-muted/30">
      <div className="container mx-auto px-6">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Everything You Need to
            <span className="text-gradient"> Learn Effectively</span>
          </h2>
          <p className="text-lg text-muted-foreground">
            Powered by advanced AI to make learning interactive, personal, and enjoyable.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {features.map((feature, index) => (
            <div
              key={feature.title}
              className="group p-6 rounded-2xl bg-card shadow-card hover:shadow-lg transition-all duration-300 hover:-translate-y-1"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className={`inline-flex p-3 rounded-xl ${feature.bgColor} mb-4`}>
                <feature.icon className={`w-6 h-6 ${feature.color}`} />
              </div>
              <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
              <p className="text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
