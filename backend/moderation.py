import logging

logger = logging.getLogger(__name__)

def analyze_content(text: str):
    """
    Moderation has been disabled as per user request.
    This function now passes all videos without applying any filters.
    """
    return True, "Content Allowed"
