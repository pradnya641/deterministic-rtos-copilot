import re

def clean_context(context: str, peripheral: str = None) -> str:
    """
    Strips noise (legal disclaimers, page numbers) and filters for relevant registers.
    """
    # 1. Remove common PDF noise/disclaimers
    noise_patterns = [
        r"UM10139.*?\d{4}.*?All rights reserved\.",
        r"User manual Rev\. \d+.*? \d+.*? \d+ of \d+",
        r"NXP Semiconductors UM10139",
        r"Chapter \d+: LPC214x.*",
        r"Table \d+:.*"
    ]
    for pattern in noise_patterns:
        context = re.sub(pattern, "", context, flags=re.IGNORECASE)

    # 3. Aggressive Filtering for ADC
    if peripheral == "ADC":
        # Remove lines that only talk about AD1
        lines = context.split("\n")
        cleaned_lines = []
        for line in lines:
            # If the line contains AD1 but not AD0, it's likely noise for an ADC0 query
            if "AD1" in line and "AD0" not in line:
                continue
            # If it's a table row with both, try to strip the AD1 part
            line = re.sub(r"0xE006\s+[0-9A-F]{4}\s+AD1[A-Z]+", "", line)
            cleaned_lines.append(line)
        context = "\n".join(cleaned_lines)

    # 4. Strip garbage characters
    context = re.sub(r'[^\x00-\x7F]+', ' ', context)
    context = re.sub(r'\n{3,}', '\n\n', context).strip()
    
    return context

def extract_register_summary(context: str) -> str:
    """
    Attempts to find register names and addresses in the context and format them.
    """
    reg_pattern = r"([A-Z0-9]{3,})\s+((?:0x)?[0-9A-F]{4}\s+[0-9A-F]{4}|0x[0-9A-F]{8})"
    matches = re.findall(reg_pattern, context)
    
    if not matches:
        return ""
        
    summary = "### Key Registers Extracted:\n"
    seen = set()
    for reg, addr in matches:
        if reg not in seen and len(reg) < 10:
            summary += f"- **{reg}**: `{addr.strip()}`\n"
            seen.add(reg)
    return summary

def normalize_utf8(text: str) -> str:
    """
    Removes emojis, translates unicode arrows, and preserves standard ASCII
    and box-drawing characters for clean rendering.
    """
    if not text:
        return ""
    
    # 1. Replace unicode arrows before filtering
    text = text.replace('\u2192', '->')  # →
    text = text.replace('\u2190', '<-')  # ←
    text = text.replace('\u21d2', '=>')  # ⇒
    text = text.replace('\u21c4', '<->') # ↔
    
    # 2. Strip emoji codepoints (U+1F000 - U+1FFFF and U+2600 - U+27BF)
    text = re.sub(r'[\u2600-\u27bf]|[\U0001f000-\U0001ffff]', '', text)
    
    # 3. Preserve ASCII and Box-Drawing characters (U+2500 - U+257F)
    result = []
    import sys
    # Use console stdout encoding to check render support, fallback to utf-8 if None
    enc = sys.stdout.encoding or 'utf-8'
    
    for char in text:
        cp = ord(char)
        if cp < 128:
            result.append(char)
        elif 0x2500 <= cp <= 0x257F:
            try:
                char.encode(enc)
                result.append(char)
            except Exception:
                result.append('-')
            
    return "".join(result)


def extract_clean_c_code(markdown_text: str) -> str:
    """
    Extracts only raw C code block from markdown, removing any markdown fences,
    diff artifacts, UTF corruption, and commentary leakage.
    """
    if not markdown_text:
        return ""
    
    # 1. Clean UTF characters
    markdown_text = normalize_utf8(markdown_text)
    
    # 2. Extract C code block using regex
    pattern = re.compile(r'```c\s*(.*?)\s*```', re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(markdown_text)
    
    c_code = ""
    for m in reversed(matches):
        if '#include' in m and ('xTaskCreate' in m or 'main' in m or 'IRQHandler' in m):
            c_code = m
            break
    if not c_code and matches:
        c_code = matches[-1]
    
    if not c_code:
        # Fallback: if no markdown fences, look for the first #include
        idx = markdown_text.find("#include")
        if idx != -1:
            c_code = markdown_text[idx:]
        else:
            c_code = markdown_text

    # 3. Clean up diff artifacts if any leaked
    cleaned_lines = []
    for line in c_code.splitlines():
        if (line.startswith("+") or line.startswith("-")) and not (line.startswith("++") or line.startswith("--")):
            # If the next characters look like C code, strip the diff indicator
            stripped = line[1:].strip()
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            cleaned_lines.append(line[1:])
        else:
            cleaned_lines.append(line)
            
    c_code = "\n".join(cleaned_lines)
    return c_code.strip()
