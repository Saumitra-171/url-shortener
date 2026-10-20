def classify_browser(user_agent: str | None) -> str:
    """Rough browser family from a User-Agent string. This is a heuristic, not an exact science."""
    if not user_agent:
        return "Unknown"
    ua = user_agent.lower()
    if any(token in ua for token in ("bot", "crawler", "spider", "curl/", "wget", "python-requests", "httpx", "postman")):
        return "Bot/Tool"
    # ORDER MATTERS. Edge and Opera also say "Chrome", and Chrome also says "Safari",
    # so the most specific names must be checked first.
    if "edg/" in ua or "edga/" in ua or "edgios/" in ua or "edge/" in ua:
        return "Edge"
    if "opr/" in ua or "opera" in ua:
        return "Opera"
    if "firefox" in ua or "fxios" in ua:
        return "Firefox"
    if "chrome" in ua or "crios" in ua:
        return "Chrome"
    if "safari" in ua:
        return "Safari"
    return "Other"