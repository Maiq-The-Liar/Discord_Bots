import random
import re
from difflib import SequenceMatcher

from repositories.quiz_repository import QuizRepository
from repositories.casual_quiz_repository import CasualQuizRepository


class CasualQuizService:
    def __init__(
        self,
        quiz_repo: QuizRepository,
        casual_quiz_repo: CasualQuizRepository,
    ):
        self.quiz_repo = quiz_repo
        self.casual_quiz_repo = casual_quiz_repo

    def normalize_answer(self, text: str) -> str:
        text = text.casefold().strip()
        text = text.replace("’", "'")
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def tokenize(self, text: str) -> list[str]:
        normalized = self.normalize_answer(text)
        if not normalized:
            return []
        return normalized.split()

    def edit_distance_leq_one(self, a: str, b: str) -> bool:
        if a == b:
            return True

        len_a = len(a)
        len_b = len(b)

        if abs(len_a - len_b) > 1:
            return False

        # Same length -> allow one substitution
        if len_a == len_b:
            mismatches = sum(ch1 != ch2 for ch1, ch2 in zip(a, b))
            return mismatches <= 1

        # Length differs by 1 -> allow one insertion/deletion
        if len_a > len_b:
            longer, shorter = a, b
        else:
            longer, shorter = b, a

        i = 0
        j = 0
        edits = 0

        while i < len(longer) and j < len(shorter):
            if longer[i] == shorter[j]:
                i += 1
                j += 1
            else:
                edits += 1
                if edits > 1:
                    return False
                i += 1

        # If one trailing char remains in the longer word, that counts as one edit
        if i < len(longer):
            edits += 1

        return edits <= 1

    def words_match(self, required_word: str, candidate_token: str) -> bool:
        if required_word == candidate_token:
            return True

        # For short words, require exact match to avoid too many false positives.
        if len(required_word) <= 3:
            return False

        return self.edit_distance_leq_one(required_word, candidate_token)

    def word_similarity(self, required_word: str, candidate_token: str) -> float:
        if not required_word or not candidate_token:
            return 0.0
        return SequenceMatcher(None, required_word, candidate_token).ratio()

    def words_partially_match(self, required_word: str, candidate_token: str) -> bool:
        """Return True when a token is close, but not close enough to be correct.

        The normal correct-answer check is intentionally still stricter: exact
        match for short words, and one edit allowed for longer words. This helper
        is only used to decide whether to react with a yellow circle instead of a
        red circle.
        """
        if self.words_match(required_word, candidate_token):
            return True

        len_required = len(required_word)
        len_candidate = len(candidate_token)
        if len_required <= 2 or len_candidate <= 1:
            return False

        # Very short answers such as "nox" should only be treated as partial
        # when the guess is a clear prefix/same-start attempt, not just a random
        # short word that happens to be similar.
        if len_required <= 3:
            return (
                required_word[0] == candidate_token[0]
                and min(len_required, len_candidate) >= 2
                and self.word_similarity(required_word, candidate_token) >= 0.80
            )

        # Longer words can be yellow when they are recognisably close, but too
        # typo-heavy to pass the existing lenient correct-answer check.
        length_gap = abs(len_required - len_candidate)
        if length_gap > max(2, len_required // 2):
            return False

        return self.word_similarity(required_word, candidate_token) >= 0.68

    def group_matches(self, required_words: list[str], candidate_tokens: list[str]) -> bool:
        if not required_words:
            return False

        for required_word in required_words:
            if not any(self.words_match(required_word, token) for token in candidate_tokens):
                return False

        return True

    def group_partially_matches(self, required_words: list[str], candidate_tokens: list[str]) -> bool:
        if not required_words or not candidate_tokens:
            return False

        stop_words = {"a", "an", "and", "for", "in", "of", "on", "the", "to"}
        significant_words = [
            word for word in required_words
            if len(word) > 3 or word not in stop_words
        ]
        words_to_check = significant_words or required_words

        strong_matches = 0
        weak_matches = 0
        for required_word in words_to_check:
            if any(self.words_match(required_word, token) for token in candidate_tokens):
                strong_matches += 1
                weak_matches += 1
            elif any(self.words_partially_match(required_word, token) for token in candidate_tokens):
                weak_matches += 1

        if weak_matches == 0:
            return False

        # Multi-word answers should become yellow when the user has one important
        # word right but is missing the rest, or when roughly half the important
        # words are recognisable through heavier typos.
        if len(words_to_check) > 1:
            return strong_matches >= 1 or weak_matches / len(words_to_check) >= 0.5

        # Single-word answers should become yellow only for a recognisably close
        # attempt, not for unrelated words.
        return weak_matches == 1

    def build_answer_groups(self, question: dict) -> list[list[str]]:
        groups: list[list[str]] = []

        # New format:
        # "answer_groups": [
        #   ["rowena", "ravenclaw"],
        #   ["salazar", "slytherin"]
        # ]
        raw_groups = question.get("answer_groups")
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if isinstance(group, list):
                    words = []
                    for item in group:
                        if isinstance(item, str):
                            words.extend(self.tokenize(item))
                    if words:
                        groups.append(words)

        # Backward compatibility with old format:
        # "answers": ["severus snape", "snape", "severus"]
        raw_answers = question.get("answers")
        if isinstance(raw_answers, list):
            for answer in raw_answers:
                if isinstance(answer, str):
                    words = self.tokenize(answer)
                    if words:
                        groups.append(words)

        return groups

    def get_next_question(self, channel_id: int) -> dict:
        all_questions = self.quiz_repo.get_all()
        if not all_questions:
            raise ValueError("No quiz questions available.")

        asked_ids = self.casual_quiz_repo.get_asked_question_ids(channel_id)
        available = [q for q in all_questions if int(q["id"]) not in asked_ids]

        if not available:
            self.casual_quiz_repo.clear_history(channel_id)
            available = all_questions

        chosen = random.choice(available)
        question_id = int(chosen["id"])

        self.casual_quiz_repo.mark_question_asked(channel_id, question_id)
        self.casual_quiz_repo.set_current_question(channel_id, question_id)

        return chosen

    def get_current_question(self, channel_id: int) -> dict | None:
        state = self.casual_quiz_repo.get_channel_state(channel_id)
        if state is None or state["current_question_id"] is None:
            return None

        return self.quiz_repo.get_by_id(int(state["current_question_id"]))

    def judge_answer(self, question: dict, message_content: str) -> str:
        """Classify an answer as correct, partial, or wrong.

        Returns:
            "correct": all required words in an accepted answer group match,
                using the existing typo-lenient matching.
            "partial": the answer is clearly on the right track, but missing
                required words or has too many typos to count as correct.
            "wrong": no accepted answer group is recognisably matched.
        """
        candidate_tokens = self.tokenize(message_content)
        if not candidate_tokens:
            return "wrong"

        answer_groups = self.build_answer_groups(question)
        if not answer_groups:
            return "wrong"

        if any(self.group_matches(group, candidate_tokens) for group in answer_groups):
            return "correct"

        if any(self.group_partially_matches(group, candidate_tokens) for group in answer_groups):
            return "partial"

        return "wrong"

    def is_correct_answer(self, question: dict, message_content: str) -> bool:
        return self.judge_answer(question, message_content) == "correct"
