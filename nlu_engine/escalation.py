def escalate_to_human(user_input, fallback_count):
    text = user_input.lower()

    if "agent" in text or "human" in text:
        return True

    if fallback_count >= 3:
        return True

    return False
