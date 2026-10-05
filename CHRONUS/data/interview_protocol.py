"""
CHRONUS Interview Protocol — 25 Questions across 6 Personality Dimensions

Based on the CHRONUS paper's structured interview augmentation for capturing
personality dimensions absent from documentary evidence.

Usage:
    from data.interview_protocol import get_all_questions, get_questions_by_dimension
"""

from typing import Optional

INTERVIEW_QUESTIONS = {
    "personality": {
        "label": "Personality & Self-Description",
        "description": "Core personality traits, habits, behavioral patterns",
        "questions": [
            {
                "id": "Q1",
                "question": "How would you describe your core personality in a few sentences?",
                "sub_dimension": "self_description",
                "prompt_hint": "Look for: self-awareness, how they see themselves vs how others see them"
            },
            {
                "id": "Q2",
                "question": "What are your most distinctive habits or quirks that people notice about you?",
                "sub_dimension": "habits",
                "prompt_hint": "Look for: repeated behaviors, known patterns, things people comment on"
            },
            {
                "id": "Q3",
                "question": "How do you typically react under extreme pressure or stress?",
                "sub_dimension": "stress_response",
                "prompt_hint": "Look for: fight/flight/freeze tendencies, coping mechanisms, documented examples"
            },
            {
                "id": "Q4",
                "question": "Would you say you're more of an optimist or a realist? How does that shape your worldview?",
                "sub_dimension": "outlook",
                "prompt_hint": "Look for: stated philosophy, evidence in decision-making patterns"
            }
        ]
    },

    "core_memories": {
        "label": "Core Memories & Defining Experiences",
        "description": "Life events that fundamentally shaped the person",
        "questions": [
            {
                "id": "Q5",
                "question": "What experience or period in your life most fundamentally shaped who you are today?",
                "sub_dimension": "defining_experience",
                "prompt_hint": "Look for: childhood, pivotal moments, turning points"
            },
            {
                "id": "Q6",
                "question": "What's a decision you made that most people thought was crazy, but you knew was right?",
                "sub_dimension": "contrarian_decision",
                "prompt_hint": "Look for: documented controversial decisions, bet-the-company moments"
            },
            {
                "id": "Q7",
                "question": "What's the hardest thing you've ever had to do professionally or personally?",
                "sub_dimension": "hardest_challenge",
                "prompt_hint": "Look for: documented difficult periods, layoffs, crises"
            },
            {
                "id": "Q8",
                "question": "Is there a moment that still affects you deeply when you think about it?",
                "sub_dimension": "emotional_memory",
                "prompt_hint": "Look for: regrets, losses, moments of significance"
            }
        ]
    },

    "relationships": {
        "label": "Relationships & Social Dynamics",
        "description": "Family, friendships, partnerships, collaboration style",
        "questions": [
            {
                "id": "Q9",
                "question": "Who has been the most influential person in your life and why?",
                "sub_dimension": "key_influence",
                "prompt_hint": "Look for: mentors, family members, collaborators frequently mentioned"
            },
            {
                "id": "Q10",
                "question": "How would your closest friends or family describe you?",
                "sub_dimension": "perceived_by_others",
                "prompt_hint": "Look for: quotes from family/friends, contrast with self-description"
            },
            {
                "id": "Q11",
                "question": "What do you value most in your relationships with people?",
                "sub_dimension": "relationship_values",
                "prompt_hint": "Look for: stated values, behavior patterns in relationships"
            },
            {
                "id": "Q12",
                "question": "How has your approach to collaboration or partnerships evolved over time?",
                "sub_dimension": "collaboration_evolution",
                "prompt_hint": "Look for: early vs recent collaboration style, documented changes"
            }
        ]
    },

    "passions": {
        "label": "Passions & Interests",
        "description": "What drives them beyond work, hobbies, intellectual pursuits",
        "questions": [
            {
                "id": "Q13",
                "question": "What gets you genuinely excited to wake up in the morning?",
                "sub_dimension": "daily_motivation",
                "prompt_hint": "Look for: stated motivations, energy patterns in interviews"
            },
            {
                "id": "Q14",
                "question": "Outside of your main work, what do you spend time thinking about or doing?",
                "sub_dimension": "outside_interests",
                "prompt_hint": "Look for: hobbies, side projects, casual mentions"
            },
            {
                "id": "Q15",
                "question": "What topic could you talk about for hours without getting bored?",
                "sub_dimension": "deep_interest",
                "prompt_hint": "Look for: topics where they elaborate at length"
            },
            {
                "id": "Q16",
                "question": "What's something you've always wanted to explore but haven't had the chance to?",
                "sub_dimension": "unexplored_interest",
                "prompt_hint": "Look for: stated aspirations, 'would love to' statements"
            }
        ]
    },

    "beliefs_values": {
        "label": "Beliefs & Values",
        "description": "Core philosophy, ethics, worldview, principles",
        "questions": [
            {
                "id": "Q17",
                "question": "What principle or belief would you never compromise on, no matter the cost?",
                "sub_dimension": "core_principle",
                "prompt_hint": "Look for: stated non-negotiables, documented stands"
            },
            {
                "id": "Q18",
                "question": "How do you think about ethics when making difficult decisions?",
                "sub_dimension": "ethical_framework",
                "prompt_hint": "Look for: how they justify controversial decisions"
            },
            {
                "id": "Q19",
                "question": "What's your view on the purpose of human existence or civilization?",
                "sub_dimension": "worldview",
                "prompt_hint": "Look for: philosophical statements, long-term thinking"
            },
            {
                "id": "Q20",
                "question": "What do you think people fundamentally misunderstand about you?",
                "sub_dimension": "misunderstanding",
                "prompt_hint": "Look for: 'people think X but actually Y' patterns, corrections"
            }
        ]
    },

    "voice_communication": {
        "label": "Voice & Communication Style",
        "description": "How they talk, vocabulary, tone, patterns",
        "questions": [
            {
                "id": "Q21",
                "question": "How would you describe your communication style?",
                "sub_dimension": "style_description",
                "prompt_hint": "Look for: self-awareness about how they communicate"
            },
            {
                "id": "Q22",
                "question": "What words or phrases do you use frequently that feel distinctly 'you'?",
                "sub_dimension": "signature_vocabulary",
                "prompt_hint": "Look for: repeated phrases, verbal tics, catchphrases"
            },
            {
                "id": "Q23",
                "question": "Do you tend to be more direct or more diplomatic? Give an example.",
                "sub_dimension": "directness",
                "prompt_hint": "Look for: documented blunt vs diplomatic moments"
            },
            {
                "id": "Q24",
                "question": "How do you usually end a conversation or close a thought?",
                "sub_dimension": "closing_patterns",
                "prompt_hint": "Look for: repeated endings, signature sign-offs"
            },
            {
                "id": "Q25",
                "question": "What tone do you naturally default to — serious, humorous, sarcastic, philosophical?",
                "sub_dimension": "default_tone",
                "prompt_hint": "Look for: dominant mood across interviews, tonal shifts"
            }
        ]
    }
}


def get_all_questions() -> list[dict]:
    """Get all 25 questions in order (Q1-Q25)."""
    all_questions = []
    for dimension_data in INTERVIEW_QUESTIONS.values():
        all_questions.extend(dimension_data["questions"])
    return all_questions


def get_questions_by_dimension(dimension: str) -> list[dict]:
    """Get questions for a specific dimension."""
    dim_data = INTERVIEW_QUESTIONS.get(dimension)
    if dim_data:
        return dim_data["questions"]
    return []


def get_question_by_id(question_id: str) -> Optional[dict]:
    """Get a specific question by its ID (e.g., 'Q7')."""
    for q in get_all_questions():
        if q["id"] == question_id:
            return q
    return None


def get_dimension_summary() -> dict:
    """Get summary of all dimensions with question counts."""
    return {
        dim_id: {
            "label": data["label"],
            "description": data["description"],
            "question_count": len(data["questions"]),
            "question_ids": [q["id"] for q in data["questions"]]
        }
        for dim_id, data in INTERVIEW_QUESTIONS.items()
    }


def format_qa_for_embedding(question: dict, answer: str) -> str:
    """Format a Q&A pair as a single text for embedding.

    The formatted text makes interview responses retrievable when
    users ask related questions.

    Example output:
        "[Interview Response] Q: How would you describe your personality?
         A: I'm an engineer at heart. I spend most of my time..."
    """
    return f"[Interview Response] Q: {question['question']} A: {answer}"


def build_interview_metadata(question: dict, dimension: str) -> dict:
    """Build ChromaDB metadata for an interview response."""
    return {
        "source_file": "interview_protocol",
        "source_type": "interview_protocol",
        "source_name": "Structured Interview",
        "date": "protocol",
        "topic": "",
        "importance_score": 4,  # High importance - direct personality capture
        "memory_id": "",  # Will be set by caller (MD5 of formatted text)
        "person": "elon_musk",
        "question_id": question["id"],
        "dimension": dimension,
        "sub_dimension": question["sub_dimension"],
        "chunk_index": 0,
        "total_chunks": 1,
        "parent_text": question["question"][:200]
    }


if __name__ == "__main__":
    # Demo: print all questions
    summary = get_dimension_summary()
    print("CHRONUS Interview Protocol — 25 Questions\n")

    for dim_id, info in summary.items():
        print(f"\n{info['label']} ({len(info['question_ids'])} questions)")
        print(f"  {info['description']}")
        for q_id in info['question_ids']:
            q = get_question_by_id(q_id)
            print(f"  {q['id']}: {q['question']}")

    print(f"\nTotal: {len(get_all_questions())} questions")


