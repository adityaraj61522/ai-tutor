import { Upload, MessageSquare, Hand, CheckCircle } from "lucide-react";

const steps = [
  {
    step: 1,
    icon: Upload,
    title: "Upload Your Material",
    description: "Upload any document – PDF, notes, or textbook chapters you want to learn.",
  },
  {
    step: 2,
    icon: MessageSquare,
    title: "Choose Your Topic",
    description: "Tell the AI what specific topic or concept you want to master.",
  },
  {
    step: 3,
    icon: Hand,
    title: "Learn Interactively",
    description: "Listen to your AI tutor explain, raise your hand anytime to ask questions.",
  },
  {
    step: 4,
    icon: CheckCircle,
    title: "Master the Content",
    description: "Get personalized explanations until you fully understand the material.",
  },
];

export const HowItWorks = () => {
  return (
    <section className="py-24">
      <div className="container mx-auto px-6">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            How It <span className="text-gradient">Works</span>
          </h2>
          <p className="text-lg text-muted-foreground">
            Start learning in minutes with our simple 4-step process.
          </p>
        </div>

        <div className="max-w-4xl mx-auto">
          <div className="grid md:grid-cols-2 gap-8">
            {steps.map((step, index) => (
              <div
                key={step.step}
                className="relative flex gap-4 p-6 rounded-2xl bg-card shadow-card"
              >
                {/* Step number */}
                <div className="flex-shrink-0 w-12 h-12 rounded-full gradient-hero flex items-center justify-center text-primary-foreground font-bold text-lg">
                  {step.step}
                </div>
                
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <step.icon className="w-5 h-5 text-primary" />
                    <h3 className="text-lg font-semibold">{step.title}</h3>
                  </div>
                  <p className="text-muted-foreground">{step.description}</p>
                </div>

                {/* Connector line */}
                {index < steps.length - 1 && index % 2 === 0 && (
                  <div className="hidden md:block absolute top-1/2 -right-4 w-8 h-0.5 bg-border" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};
