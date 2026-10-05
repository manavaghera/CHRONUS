const features = [
  {
    title: "Smart Scheduling",
    desc: "AI-powered time-boxing that respects energy levels, time zones, and meeting load across your team.",
    icon: "01",
  },
  {
    title: "Dependency Graph",
    desc: "See every blocked and blocking task in real time. No more surprises at sprint review.",
    icon: "02",
  },
  {
    title: "Async Standups",
    desc: "Automated daily check-ins that replace 30-minute meetings with a 2-minute written update.",
    icon: "03",
  },
  {
    title: "Velocity Insights",
    desc: "Track team throughput over time. Spot trends before they become problems.",
    icon: "04",
  },
  {
    title: "Calendar Shield",
    desc: "Protects focus blocks and deep work time. Declines meetings that violate your team's rhythm.",
    icon: "05",
  },
  {
    title: "Release Tracker",
    desc: "One view for every upcoming release. See what's ready, what's at risk, and what's been cut.",
    icon: "06",
  },
];

export default function Features() {
  return (
    <section id="features" style={{ padding: "8rem 1.5rem" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <p
          style={{
            color: "#c8ff00",
            fontSize: "0.8rem",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            marginBottom: "1rem",
          }}
        >
          Features
        </p>
        <h2
          style={{
            fontSize: "clamp(2rem, 5vw, 3.5rem)",
            fontWeight: 700,
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
            maxWidth: 500,
            marginBottom: "4rem",
          }}
        >
          Everything your team needs. Nothing it doesn't.
        </h2>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "1px",
            background: "#222",
            borderRadius: "var(--radius)",
            overflow: "hidden",
          }}
        >
          {features.map((f) => (
            <div
              key={f.title}
              style={{
                padding: "2.5rem",
                background: "#0a0a0a",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: 36,
                  height: 36,
                  lineHeight: "36px",
                  textAlign: "center",
                  borderRadius: 8,
                  background: "#1a1a1a",
                  fontSize: "0.8rem",
                  fontWeight: 700,
                  color: "#c8ff00",
                  marginBottom: "1.25rem",
                }}
              >
                {f.icon}
              </span>
              <h3 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                {f.title}
              </h3>
              <p style={{ color: "#888", fontSize: "0.9rem", lineHeight: 1.6 }}>
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
