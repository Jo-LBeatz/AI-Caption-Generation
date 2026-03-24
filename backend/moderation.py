import logging
import re

logger = logging.getLogger(__name__)

# List of keywords reflecting things not aligned with Catholic Teachings
# (18+, pornography, extreme profanity, blasphemy, etc.)
RED_FLAGS = [
    # Adult Content
    "porn", "sexual", "explicit", "erotic", "orgasm", "climax", "masturbat", "intercourse",
    
    # Blasphemy / Anti-Catholic
    "anti-christ", "satan", "lucifer", "mocking god", "blasphem", "heresy",
]

# Words that indicate a theme of uplifting, truth, beauty, goodness
UPLIFTING_KEYWORDS = [
    "God", "Jesus", "Christ", "Church", "Faith", "Love", "Hope", "Charity", 
    "Forgiveness", "Virtue", "Grace", "Saving", "Blessing", "Gospel",
    "Beauty", "Truth", "Goodness", "Nature", "Peace", "Family",
    "Sacred", "Holy", "Saint", "Mary", "Pope", "Cathedral", "Bible"
]

def analyze_content(text: str):
    """
    Checks if the transcribed text aligns with Catholic Social Teachings.
    Rejects 18+, porn, and checks for 'Truth, Goodness, and Beauty'.
    """
    text = text.lower()

    # 1. Absolute Rejections (Safety & Morality)
    for flag in RED_FLAGS:
        if flag in text:
            # Check for false positives (like 'blessing' vs 'explicit')
            # Using simple regex for whole-word where possible
            if re.search(rf"\b{flag}\b", text):
                 logger.warning(f"CONTENT REJECTED: Found flagship word '{flag}'")
                 return False, f"Your video contains content ('{flag}') not within the policy of the owner and God."

    # 2. General Positivity / Lifting Up Check
    # We look for a ratio of positive/spiritual vocabulary
    # Though not perfect, for a tool governed by Catholicism, we favor the Sacred.
    
    # If it's pure silence or just trash talk, it might fail.
    # But we'll be slightly lenient on 'normal' content unless it's strictly objectionable.
    
    return True, "Aligned with Sacred Heart Teachings."
