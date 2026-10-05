import { useState, useEffect } from "react";

const quotes = [
  {
    text: "Chronus replaced four tools for us. Our sprint planning meetings went from 90 minutes to 15.",
    author: "Sarah Chen",
    role: "VP Engineering, Arcline",
  },
  {
    text: "For the first time, I can actually see where the bottlenecks are before they blow up a release.",
    author: "Marcus Rivera",
    role: "Product Lead, Stellate",
  },
  {
    text: "The async standup feature alone saved us 5+ hours a week across the team.",
    author: "Priya Sharma",
    role: "CTO, Waveloop",
  },
];

export default function QuoteRotator() {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrent((prev) => (prev + 1) % quotes.length);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const q = quotes[current];

  return (
    <section
      style={{
        padding: "8rem 1.5rem",
        display: "flex",
        justifyContent: "center",
      }}
    >
      <div style={{ maxWidth: 700, textAlign: "center" }}>
        <div
          style={{
            fontSize: "3rem",
            color: "#333",
            lineHeight: 1,
            marginBottom: "1.5rem",
          }}
        >
          "
        </div>
        <p
          key={current}
          style={{
            fontSize: "clamp(1.25rem, 3vw, 1.75rem)",
            fontWeight: 500,
            lineHeight: 1.5,
            marginBottom: "2rem",
            animation: "fadeIn 0.5s ease",
          }}
        >
          {q.text}
        </p>
        <div>
          <p style={{ fontWeight: 600, fontSize: "0.95rem" }}>{q.author}</p>
          <p style={{ color: "#888", fontSize: "0.85rem" }}>{q.role}</p>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: "0.5rem",
            marginTop: "2rem",
          }}
        >
          {quotes.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: i === current ? "#c8ff00" : "#333",
                transition: "background 0.3s",
              }}
              aria-label={`Quote ${i + 1}`}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
