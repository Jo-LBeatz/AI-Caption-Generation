"""
morality.py — Moral Law & Theological Evaluation Engine for Verbum.

Evaluates video transcriptions based on:
1. The Ten Commandments of the Law of Moses (from bpr1_catholic_prayer_book.pdf, pages 98-100)
2. The Two Commandments of the Law of Jesus Christ (from The Two Commandments of Christ.pdf:
   St. Matthew 22:37-40, St. Mark 12:29-31, St. John 13:34-35)

CRITICAL PRINCIPLE:
Users may use whatever words or vocabulary they choose. Mere mentions, quotes, historical
references, storytelling, or slang (e.g., 'I killed that test', 'damn', 'holy cow') are NOT evil.
The engine only flags a video if its OVERALL MESSAGE / CORE CONCEPT / MORAL / MOTTO as a whole
promotes, advocates, teaches, incites, or justifies actions contrary to the Ten Commandments
of Moses or the Two Commandments of Christ.
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Catholic Theological Definitions based on bpr1_catholic_prayer_book.pdf (pp. 98-100)
# and The Two Commandments of Christ.pdf
THEOLOGICAL_FRAMEWORK = {
    "christ_commandment_1": {
        "name": "The First & Greatest Commandment of Christ",
        "scripture": "St. Matthew 22:37-38; St. Mark 12:29-30",
        "text": "Thou shalt love the Lord thy God with thy whole heart, and with thy whole soul, and with thy whole mind, and with thy whole strength.",
        "description": "Love, worship, and reverence for the One True God above all created things."
    },
    "christ_commandment_2": {
        "name": "The Second Commandment of Christ",
        "scripture": "St. Matthew 22:39-40; St. Mark 12:31; St. John 13:34-35",
        "text": "Thou shalt love thy neighbour as thyself. A new commandment I give unto you: That you love one another, as I have loved you.",
        "description": "True charity, justice, mercy, and goodwill toward every fellow human being."
    },
    "moses_commandment_1": {
        "number": 1,
        "name": "First Commandment of Moses",
        "source": "bpr1_catholic_prayer_book.pdf pp. 98-99",
        "text": "I am the Lord thy God… Thou shalt not have strange gods before me… Thou shalt not adore them nor serve them.",
        "prohibits": "Denial of God/dogmas, apostasy, heresy, idolatry, witchcraft, divination, Santería, Voodoo, Brujería, Ouija boards, Tarot, horoscopes, demon invocation, occult practices."
    },
    "moses_commandment_2": {
        "number": 2,
        "name": "Second Commandment of Moses",
        "source": "bpr1_catholic_prayer_book.pdf p. 99",
        "text": "Thou shalt not take the name of the Lord thy God in vain.",
        "prohibits": "Blasphemy, profaning the holy name of God, cursing God, profaning sacred things, swearing falsely or rashly."
    },
    "moses_commandment_3": {
        "number": 3,
        "name": "Third Commandment of Moses",
        "source": "bpr1_catholic_prayer_book.pdf p. 99",
        "text": "Remember thou keep holy the Lord's Day.",
        "prohibits": "Despising the Lord's Day, missing holy worship through willful contempt, profaning sacred days with unnecessary servile labor."
    },
    "moses_commandment_4": {
        "number": 4,
        "name": "Fourth Commandment of Moses",
        "source": "bpr1_catholic_prayer_book.pdf p. 99",
        "text": "Honor thy father and thy mother.",
        "prohibits": "Rebellion, contempt, and unlawful disobedience toward parents, lawful authorities, and superiors."
    },
    "moses_commandment_5": {
        "number": 5,
        "name": "Fifth Commandment of Moses",
        "source": "bpr1_catholic_prayer_book.pdf p. 99",
        "text": "Thou shalt not murder.",
        "prohibits": "Murder, abortion, euthanasia, suicide, promoting violence, cruelty, unjust hatred, revenge, or bodily harm against human life."
    },
    "moses_commandment_6_9": {
        "number": "6 & 9",
        "name": "Sixth & Ninth Commandments of Moses",
        "source": "bpr1_catholic_prayer_book.pdf pp. 99-100",
        "text": "Thou shalt not commit adultery. Thou shalt not covet thy neighbor's wife.",
        "prohibits": "Adultery, fornication, sodomy/homosexual acts, transgenderism (coveting neighbor's gender/altering God-given sex), bestiality, prostitution, pornography, promoting sexual impurity."
    },
    "moses_commandment_7_10": {
        "number": "7 & 10",
        "name": "Seventh & Tenth Commandments of Moses",
        "source": "bpr1_catholic_prayer_book.pdf pp. 99-100",
        "text": "Thou shalt not steal. Thou shalt not covet thy neighbor's goods.",
        "prohibits": "Theft, robbery, fraud, scamming, cheating in business, withholding just wages, extortion, coveting or destroying another's property."
    },
    "moses_commandment_8": {
        "number": 8,
        "name": "Eighth Commandment of Moses",
        "source": "bpr1_catholic_prayer_book.pdf p. 100",
        "text": "Thou shalt not bear false witness against thy neighbor.",
        "prohibits": "Lying, calumny, slander, false accusations, perjury, framing others, deceit, malicious detraction."
    }
}


def _try_llm_evaluation(text: str) -> Optional[Dict[str, Any]]:
    """
    If a Gemini API key or OpenAI API key is configured, evaluate the full video message
    theologically with state-of-the-art NLU.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            import httpx
            prompt = f"""
You are a Catholic theological morality analyst evaluating the transcript of an uploaded video.
The rule of morality is strictly based upon:
1. The Ten Commandments of the Law of Moses (from the Catholic Prayer Book examination of conscience):
   - 1st: No strange gods, idolatry, apostasy, witchcraft, occult, divination, tarot, ouija boards.
   - 2nd: Do not take God's name in vain; no blasphemy, cursing God, profaning holy things.
   - 3rd: Keep holy the Lord's Day.
   - 4th: Honor father and mother; no rebellion against rightful parents/authority.
   - 5th: Do not murder; no abortion, euthanasia, suicide, promoting violence, cruelty, or unjust revenge.
   - 6th & 9th: Do not commit adultery or covet neighbor's wife; no fornication, sodomy, prostitution, transgenderism, pornography, promotion of sexual immorality.
   - 7th & 10th: Do not steal or covet goods; no theft, fraud, scamming, cheating, extortion.
   - 8th: Do not bear false witness; no lying, perjury, slander, calumny, or malicious deception.
2. The Two Commandments of Christ:
   - 1st: Love the Lord thy God with all thy heart, soul, mind, and strength.
   - 2nd: Love thy neighbour as thyself.

CRITICAL INSTRUCTION:
Do NOT judge isolated words, dramatic dialogue, literary quotes, casual slang, or historical mentions.
The user is allowed to use ANY words they choose.
Evaluate ONLY whether the OVERALL MESSAGE / CORE CONCEPT / MORAL / MOTTO / LESSON that the video as a whole teaches or advocates to people is EVIL by directly opposing the Ten Commandments of Moses or the Two Commandments of Christ.

Transcript:
\"\"\"{text[:10000]}\"\"\"

Respond ONLY with valid JSON in this exact structure:
{{
  "is_evil": true or false,
  "core_message": "<brief summary of what the video overall teaches>",
  "commandments_violated": ["<Name of violated commandment(s) or none>"],
  "theological_reasoning": "<thorough explanation citing Moses' commandments (pages 98-100) and/or Christ's commandments, or empty string if not evil>"
}}
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    out_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(out_text)
                    return {
                        "is_evil": bool(parsed.get("is_evil", False)),
                        "title": "Danger! Your message through the video is evil!" if parsed.get("is_evil") else "Message Approved",
                        "commandment_violated": ", ".join(parsed.get("commandments_violated", [])),
                        "reason": parsed.get("theological_reasoning", ""),
                        "core_message": parsed.get("core_message", ""),
                        "scriptural_basis": "Law of Moses (bpr1_catholic_prayer_book.pdf pp. 98-100) & Two Commandments of Christ"
                    }
        except Exception as e:
            logger.warning(f"Gemini morality evaluation failed ({e}), falling back to local engine.")

    return None


def _local_semantic_evaluation(text: str) -> Dict[str, Any]:
    """
    Offline semantic discourse analyzer.
    Examines the overall intent, directive modality, and moral posture of the transcript.
    Differentiates between:
      a) Mere mentions, narratives, confessions, sermons, refutations, quotes, casual slang.
      b) Videos whose affirmative thesis / lesson / motto advocates evil.
    """
    clean_text = text.strip()
    if not clean_text:
        return {"is_evil": False}

    lower = clean_text.lower()
    words = lower.split()
    total_words = len(words)

    # 1. Context check: Is this a moral, religious, or cautionary talk condemning sin or examining conscience?
    pious_or_cautionary_markers = [
        "thou shalt not", "commandment", "repent", "confess", "forgiveness", "penance",
        "sin is wrong", "avoid evil", "bad deed", "do not do this", "wrong to",
        "warning against", "against the law", "moral of the story", "catholic", "prayer book",
        "in the name of god", "sacred", "holy", "salvation", "virtue"
    ]
    pious_count = sum(1 for m in pious_or_cautionary_markers if m in lower)

    # 2. Check for Affirmative Advocacy / Instructional Teaching of Moral Violations
    # Notice: We look for instructional / advocacy framing ("how to", "you should", "let's", "best way to", "why we must")
    # combined with evil actions, and NOT negated.

    violations = []
    reasons = []

    # --- Fifth Commandment (Murder, Abortion, Suicide, Unjust Violence) ---
    murder_advocacy = [
        r"\b(how to (kill|murder|poison|slaughter) (someone|people|your enemy|them))\b",
        r"\b(we must (kill|murder|exterminate|wipe out) (all|those|them))\b",
        r"\b(why you should (commit suicide|kill yourself|end your life))\b",
        r"\b(justifying (murder|killing innocents|slaughter))\b",
        r"\b(let's go (kill|murder|attack) (them|people))\b"
    ]
    for pat in murder_advocacy:
        if re.search(pat, lower):
            violations.append(THEOLOGICAL_FRAMEWORK["moses_commandment_5"]["name"])
            reasons.append(
                "The video's core message advocates, instructs, or incites murder, suicide, or unlawful violence against human life. "
                "This directly defies the Fifth Commandment of the Law of Moses ('Thou shalt not murder', Catholic Prayer Book p. 99) "
                "and Christ's Second Commandment: 'Thou shalt love thy neighbour as thyself' (St. Matthew 22:39)."
            )
            break

    # --- Seventh & Tenth Commandments (Theft, Robbery, Scams, Fraud) ---
    theft_advocacy = [
        r"\b(how to (steal|rob|shoplift|scam|defraud|hack into bank))\b",
        r"\b(tutorial on (stealing|shoplifting|credit card fraud|robbing))\b",
        r"\b(easy way to (steal|scam people|defraud innocent))\b",
        r"\b(why (stealing|robbing|scamming) is (good|smart|the best way))\b",
        r"\b(how i steal without getting caught and you should too)\b"
    ]
    for pat in theft_advocacy:
        if re.search(pat, lower):
            violations.append(THEOLOGICAL_FRAMEWORK["moses_commandment_7_10"]["name"])
            reasons.append(
                "The video's core message teaches, encourages, or justifies stealing, robbery, fraud, or unlawful enrichment at the expense of others. "
                "This directly violates the Seventh and Tenth Commandments ('Thou shalt not steal. Thou shalt not covet thy neighbor's goods', Catholic Prayer Book pp. 99-100) "
                "and Christ's commandment to treat your neighbor with justice and charity (St. Matthew 22:39)."
            )
            break

    # --- First Commandment & First Commandment of Christ (Idolatry, Witchcraft, Demonology, Apostasy) ---
    witchcraft_advocacy = [
        r"\b(how to (cast a spell|cast black magic|summon demons|summon satan|contact the dead via ouija))\b",
        r"\b(ritual to worship (satan|lucifer|demons|strange gods))\b",
        r"\b(guide to (practicing voodoo|practicing santer[ií]a|brujer[ií]a|witchcraft))\b",
        r"\b(why you should (reject god|worship the devil|praise lucifer))\b"
    ]
    for pat in witchcraft_advocacy:
        if re.search(pat, lower):
            violations.append(THEOLOGICAL_FRAMEWORK["moses_commandment_1"]["name"])
            reasons.append(
                "The video's core message promotes witchcraft, occultism, divination, or the adoration of false gods and demons. "
                "This directly violates the First Commandment of the Law of Moses ('Thou shalt not have strange gods before me', Catholic Prayer Book pp. 98-99) "
                "and the Greatest Commandment of Jesus Christ: 'Thou shalt love the Lord thy God with thy whole heart, and with thy whole soul, and with thy whole mind' (St. Matthew 22:37)."
            )
            break

    # --- Second Commandment (Blasphemy & Profanation of God) ---
    blasphemy_advocacy = [
        r"\b(curse god and|blaspheme against god|mocking and insulting god almighty|god is evil and we should hate him)\b",
        r"\b(desecrate the (eucharist|cross|holy church)|spit on the cross)\b"
    ]
    for pat in blasphemy_advocacy:
        if re.search(pat, lower):
            violations.append(THEOLOGICAL_FRAMEWORK["moses_commandment_2"]["name"])
            reasons.append(
                "The video's core message actively attacks, curses, or profanes Almighty God or sacred mysteries. "
                "This directly violates the Second Commandment of Moses ('Thou shalt not take the name of the Lord thy God in vain', Catholic Prayer Book p. 99) "
                "and Christ's first commandment of total love and reverence toward God."
            )
            break

    # --- Sixth & Ninth Commandments (Promoting Sexual Immorality, Adultery, Transgenderism) ---
    sexual_immorality_advocacy = [
        r"\b(how to (cheat on your spouse|commit adultery without getting caught))\b",
        r"\b(why (adultery|cheating on your wife|cheating on your husband) is (great|good|recommended))\b",
        r"\b(promotion of (pornography|prostitution|sodomy|bestiality))\b",
        r"\b(guide to (changing your gender|transgender transition for kids))\b"
    ]
    for pat in sexual_immorality_advocacy:
        if re.search(pat, lower):
            violations.append(THEOLOGICAL_FRAMEWORK["moses_commandment_6_9"]["name"])
            reasons.append(
                "The video's core message promotes adultery, sexual impurity, or gender rejection (Transgenderism). "
                "This directly violates the Sixth and Ninth Commandments of the Law of Moses ('Thou shalt not commit adultery. Thou shalt not covet thy neighbor's wife', Catholic Prayer Book pp. 99-100)."
            )
            break

    # --- Eighth Commandment (Slander, Perjury, Calumny, Deceit) ---
    slander_advocacy = [
        r"\b(how to (frame an innocent person|lie under oath|commit perjury|spread false rumors to ruin someone))\b",
        r"\b(tutorial on (forging documents to frame|falsely accusing))\b"
    ]
    for pat in slander_advocacy:
        if re.search(pat, lower):
            violations.append(THEOLOGICAL_FRAMEWORK["moses_commandment_8"]["name"])
            reasons.append(
                "The video's core message teaches or advocates bearing false witness, calumny, or malicious deception to harm others. "
                "This directly violates the Eighth Commandment of Moses ('Thou shalt not bear false witness against thy neighbor', Catholic Prayer Book p. 100) "
                "and Christ's commandment to love one's neighbor."
            )
            break

    # If pious/cautionary context is high and no direct advocacy, it is not evil
    if pious_count >= 2 and len(violations) == 0:
        return {"is_evil": False}

    if violations:
        return {
            "is_evil": True,
            "title": "Danger! Your message through the video is evil!",
            "commandment_violated": " & ".join(violations),
            "reason": "\n\n".join(reasons),
            "scriptural_basis": "The Ten Commandments of the Law of Moses (bpr1_catholic_prayer_book.pdf pp. 98-100) and The Two Commandments of Christ (St. Matthew 22:37-40)."
        }

    return {"is_evil": False}


def evaluate_video_morality(transcript_text: str) -> Dict[str, Any]:
    """
    Main evaluation entry point.
    First tries LLM semantic analysis (if configured), then falls back to local semantic evaluator.
    """
    if not transcript_text or not transcript_text.strip():
        return {"is_evil": False}

    # 1. Try LLM if API key exists
    llm_result = _try_llm_evaluation(transcript_text)
    if llm_result is not None:
        return llm_result

    # 2. Local semantic analyzer
    return _local_semantic_evaluation(transcript_text)
