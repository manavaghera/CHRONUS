"""Question sets for calibrating the "I don't know" fallback (evaluation/run_eval.py,
figures/build_figures.py). No heavy imports, so build scripts can use them."""

# Questions he did answer (beyond the TED ones) and questions his archive
# has no documented answer to — for calibrating the "I don't know" fallback.
IN_DOMAIN_SHORT = [
    "What is the goal of SpaceX?", "Why did you buy Twitter?", "Are you worried about AI?", "How do you handle failure?",
    "Why are you so focused on manufacturing?", "What do you think about Mars?", "Tell me about your childhood",
    "What is the meaning of life?", "What do you think about electric cars?", "How do you think about first principles?",
    "What do you think about Tesla?", "How would you describe your personality?", "What is Neuralink for?", "Why Mars?",
]
OUT_OF_DOMAIN = [
    "What is your favorite pizza topping?", "How do I bake sourdough bread at home?", "What is the capital of Peru?",
    "Who won the 1983 Cricket World Cup?", "How do I fix a leaking kitchen tap?", "What's a good recipe for chicken biryani?",
    "What is your blood type?", "What was the name of your first-grade teacher?", "How many teaspoons are in a tablespoon?",
    "What's the best way to learn the violin as an adult?", "Which Bollywood actor do you like most?",
    "What did you eat for breakfast on your 30th birthday?", "How do I get rid of aphids on rose bushes?",
    "What is the plot of Pride and Prejudice?", "How tall is Mount Kilimanjaro?", "What's your favourite Taylor Swift song?",
    "How do I knit a scarf?", "What is the boiling point of ethanol?", "Which Premier League football club do you support?",
    "What's the best hiking trail in Patagonia?", "How do I file taxes in Canada as a student?",
    "What colour were the curtains in your childhood bedroom?", "How do you make a paper airplane fly farther?",
    "What's the difference between baking soda and baking powder?", "Who painted the Mona Lisa?", "What is your favourite flower?",
    "How do I train a puppy to sit?", "What's the best time to visit Kerala?", "How do you tie a bow tie?",
    "What is the population of Iceland?", "How do I make masala chai?", "What is the chemical symbol for tungsten?",
    "What is your favourite board game?", "How do I get a stain out of a silk shirt?", "Who is your favourite poet?",
    "What languages are spoken in Switzerland?", "How do I start a vegetable garden on a balcony?",
    "What is the offside rule in field hockey?", "What is your opinion on Kathak dance?", "How do I descale a kettle?",
]
