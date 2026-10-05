const steps = [
  {
    num: "01",
    title: "Connect your stack",
    body: "Plug in GitHub, Linear, Slack, and Google Calendar in under two minutes. Chronus reads your existing data — no migration required.",
  },
  {
    num: "02",
    title: "Map your workflow",
    body: "Chronus learns your sprint cadence, team size, and dependencies. It builds a living model of how your team actually works.",
  },
  {
    num: "03",
    title: "Ship with clarity",
    body: "A unified timeline gives every team member a single source of truth. Blockers surface instantly, and planning takes minutes instead of hours.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" style={{ padding: "8rem 1.5rem" }}>
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
          How It Works
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
          Three steps to total visibility.
        </h2>

        <div style={{ display: "flex", flexDirection: "column", gap: "3rem" }}>
          {steps.map((s) => (
            <div
              key={s.num}
              style={{
                display: "grid",
                gridTemplateColumns: "60px 1fr",
                gap: "2rem",
                padding: "2.5rem 0",
                borderTop: "1px solid #222",
              }}
            >
              <span style={{ fontSize: "2.5rem", fontWeight: 800, color: "#c8ff00" }}>
                {s.num}
              </span>
              <div>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                  {s.title}
                </h3>
                <p style={{ color: "#888", fontSize: "1rem", lineHeight: 1.6, maxWidth: 560 }}>
                  {s.body}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
