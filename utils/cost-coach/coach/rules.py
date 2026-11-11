"""Anti-pattern rules. Pure functions: input in -> Finding | None. No I/O.

Each rule names the billing atom it attacks (see DESIGN.md):
  TURN    = an extra agent turn re-sends the whole context (Claude tokens, Devin ACU)
  CTX     = new context is written to the cache (1.25-2x) and re-read every later call
  REBUILD = the cached prefix is lost and re-written in full
  OUTPUT  = output tokens (5x on Claude)
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Finding:
    rule: str
    billing_point: str
    message: str               # shown to the human (notification)
    agent_context: str = ""    # injected into the agent's context (optional)
    block: bool = False        # only honoured in "block" mode
    extra: dict = field(default_factory=dict)


# ---- empty / acknowledgement-only prompts -------------------------------------------------
_PUNCT = re.compile(r"[\s\.\!\?~,]+")


def _norm(text: str) -> str:
    return _PUNCT.sub(" ", text.strip().lower()).strip()


# Token-based: a prompt is "empty" when EVERY word is an acknowledgement word, so variants
# ("ㅇㅇㅇ", "넵넵", "계속해 주세요", "ok go", "sounds good, proceed", "👍") are caught while any
# concrete content ("ok, now add tests for parse_date") is not. Capped at 40 characters.
_ACK_WORDS_EN = {
    "ok", "okay", "okey", "k", "kk", "yes", "y", "yep", "yup", "yeah", "ya", "sure", "go", "ahead", "on",
    "for", "it", "please", "pls", "plz", "proceed", "continue", "keep", "going", "next", "lgtm", "do",
    "sounds", "good", "great", "fine", "cool", "nice", "perfect", "alright", "right", "thanks", "thank",
    "you", "thx", "ty", "got", "sg", "agreed", "approve", "approved", "confirm", "confirmed", "same",
    "that", "then", "let's", "lets", "and", "now",
}
# Korean: jamo-only words (ㅇㅇㅇ, ㅋㅋ, ㄱㄱ) or words starting with an acknowledgement stem
_ACK_JAMO = re.compile(r"^[ㅇㅋㄱㄴㅎㅏㅓ]+$")
_ACK_STEMS_KO = ("계속", "진행", "좋", "네", "넵", "넹", "예", "응", "웅", "오키", "오케", "옙", "그래", "그렇게",
                 "해", "하세", "하자", "고고", "확인", "감사", "고마", "부탁", "다음", "굿", "콜", "알겠", "ㅇㅋ",
                 "가자", "가즈", "시작", "ㄱ")
_EMOJI_OR_PUNCT = re.compile(r"^[\W_]+$", re.UNICODE)


# Structure signals: anything that makes a prompt a real instruction rather than a nod.
_CONTENT = re.compile(
    r"[\w\-/]+\.[a-z]{1,5}\b|`|\(\)|https?://|::|#\d+|\b\w+_\w+\b|(?-i:\b[a-z]+[A-Z]\w*\b)|\d{2,}|"
    r"\b(add|create|write|implement|build|make|fix|update|remove|delete|rename|refactor|test|run|install|"
    r"deploy|explain|why|how|what|where|show|check|use|change|move|split|merge|review)\b|"
    r"(추가|생성|작성|구현|만들|수정|고쳐|고치|삭제|제거|변경|바꿔|리팩|테스트|실행|설치|배포|설명|확인해|"
    r"보여|분리|합쳐|리뷰|왜|어떻게|무엇|뭐가|어디)", re.IGNORECASE)
_POLITE = re.compile(r"^(주세요|주십시오|줘|줘요|주라|부탁|드립니다|드려요|요|용|합니다|해요|하세요|해라|ㄱ+|please|pls)$")


def has_content(text: str) -> bool:
    return bool(_CONTENT.search(text or ""))


def _is_ack_word(w: str) -> bool:
    w = w.strip("'\"")
    if not w:
        return True
    if w in _ACK_WORDS_EN or _ACK_JAMO.match(w) or _EMOJI_OR_PUNCT.match(w) or _POLITE.match(w):
        return True
    return any(w.startswith(st) for st in _ACK_STEMS_KO)


def empty_prompt(text: str) -> Optional[Finding]:
    raw = (text or "").strip()
    t = _norm(raw)
    words = t.split()
    # (1) every word is an acknowledgement, or (2) very short with no instruction content
    #     (catches slang the word list does not know, e.g. "ㄱㄱ씽", "gogo", "ㅇㅋ 부탁드려요")
    is_ack = len(raw) <= 40 and all(_is_ack_word(w) for w in words)
    is_short = len(raw) <= 12 and len(words) <= 3 and not has_content(raw) and not is_correction(raw)
    if is_ack or is_short:
        return Finding(
            rule="empty_prompt",
            billing_point="TURN",
            message=f'"{raw[:20]}" starts a full agent turn that re-sends the whole context. '
                    "Put the next instruction in the same message.",
            agent_context=(
                "[cost-coach] The user replied with a bare acknowledgement. Treat it as approval for "
                "ALL remaining steps of the current plan: carry them out to completion (including "
                "tests and verification) without stopping to ask for confirmation again, then give "
                "one final summary."
            ),
            block=True,
        )
    return None


# ---- corrections / retries -----------------------------------------------------------------
# A correction is judged from how the prompt STARTS ("No, revert that", or the Korean equivalent),
# so ordinary requests that merely contain "no", "stop", "undo" or "wrong" are not flagged.
_CORRECTION_START = re.compile(
    r"^\s*(?:hmm+,?\s*|actually,?\s*|wait,?\s*|음+,?\s*|어+,?\s*)?("
    # Korean
    r"아니|아냐|아닌데|아뇨|아니요|그게 아니|그거 아니|그거 말고|그게 말고|이거 말고|틀렸|틀린|잘못|"
    r"다시|원래대로|되돌려|롤백|취소|이상하|안 ?되(는데|잖|네)|안돼|왜 이렇게|왜 그렇게|"
    # English
    r"no\b|nope|not quite|not that|not what|wrong|that'?s (not|wrong|incorrect)|thats not|incorrect|"
    r"undo (that|it|this|the last|your)|revert (that|it|this|the last|your)|roll ?back|try again|redo|"
    r"(you|that|this|it) (broke|broken)|still (fails|failing|broken|not|wrong|doesn'?t)|"
    r"(it|this|that) (doesn'?t|does not|didn'?t|did not) work|stop[,.!]|stop (it|that|doing)\b"
    r")",
    re.IGNORECASE,
)
_CORRECTION_ANY = re.compile(
    r"왜 .{0,12}(했|바꿨|지웠|고쳤)|그게 아니라|그게 아니고|말고 다른|원래대로|되돌려|"
    r"(방금|아까|이전|직전).{0,8}(취소|되돌|롤백|빼|없애)|"
    r"not what i (asked|wanted|meant)|i said\b|i told you|as i said",
    re.IGNORECASE)
_BUILD_REQUEST = re.compile(   # imperative "build something" requests, not "that broke the build"
    r"^\s*(please\s+)?(add|create|write|implement|build|make|generate)\b|"
    r"\b(please\s+)?(add|create|write|implement|build|make|generate) (a|an|the|one|new|some)\b|"
    r"(추가|생성|작성|구현|만들)(해|하|줘|해줘|해주세요)",
    re.IGNORECASE)
# a correction must not be an ordinary request that merely starts with these words
_NOT_CORRECTION = re.compile(
    r"^\s*(no need|no longer|nobody|none|nothing|noted|stop (the|a|an|all|any)\b|wrong(ly)? \w+ (is|are|was)|"
    r"다시 (한번 )?(설명|정리|확인)해)", re.IGNORECASE)


def is_correction(text: str) -> bool:
    t = (text or "").strip()
    if not t or _NOT_CORRECTION.search(t):
        return False
    # "취소 버튼 추가해줘", "Rollback script … write one": a cue word, but the prompt asks to BUILD something
    if _BUILD_REQUEST.search(t) and not _CORRECTION_ANY.search(t[:120]):
        return False
    return bool(_CORRECTION_START.search(t[:60]) or _CORRECTION_ANY.search(t[:120]))


def correction_streak(streak: int, threshold: int) -> Optional[Finding]:
    if streak >= threshold:
        return Finding(
            rule="correction_loop",
            billing_point="TURN+CTX",
            message=f"{streak} corrections in a row. Fixing it in this session adds a billed turn each "
                    "time and the context keeps growing. Write the requirements in one go and "
                    "start a new session (/clear).",
            agent_context=(
                "[cost-coach] The user has corrected you several times in a row. Before changing code "
                "again, restate in 3 bullet points what the user wants and what you will NOT do, "
                "then make one complete fix."
            ),
        )
    return None


# ---- several unrelated tasks bundled in one prompt ---------------------------------------
_LIST_ITEM = re.compile(r"^\s*(?:\d+[\.\)]|[-*•])\s+(.+)$", re.MULTILINE)
# Items that refer back to an earlier item are steps of ONE task, not separate tasks.
_BACKREF = re.compile(r"\b(it|that|this|them|the bug|the fix|the test|above|previous)\b|"
                      r"(그거|이거|그걸|이걸|위의|위에서|해당|그 버그|그 파일)", re.IGNORECASE)


def bundled_tasks(text: str) -> Optional[Finding]:
    items = _LIST_ITEM.findall(text or "")
    if len(items) < 4 or len(text) > 2000:
        return None
    if sum(1 for i in items if _BACKREF.search(i)) >= 1:
        return None
    n = len(items)
    return Finding(
        rule="bundled_tasks",
        billing_point="CTX",
        message=f"{n} separate tasks in one prompt. Each task's files stay in context for all the others. "
                "Separate sessions keep context small and can run in parallel.",
        extra={"tasks": n},
    )


# ---- big open-ended request without a plan -----------------------------------------------
_BIG = re.compile(
    r"(전체|전부|모두|싹 다|리팩터|리팩토링|재작성|마이그레이션|새로 만들|처음부터|"
    r"refactor|rewrite|migrate|from scratch|entire|whole codebase|all the)",
    re.IGNORECASE,
)
_SPECIFIC = re.compile(r"([\w\-/]+\.\w{1,5}\b|`[^`]+`|#\d+|https?://|::|\(\)|/[\w\-]+/)")


def vague_large(text: str) -> Optional[Finding]:
    t = text.strip()
    if t.startswith("/"):
        return None
    if _BIG.search(t) and len(t) < 160 and not _SPECIFIC.search(t):
        return Finding(
            rule="vague_large_task",
            billing_point="TURN",
            message="Large request without files or symbols. Ask for a plan first (files, steps, checks) "
                    "to avoid trial-and-error turns.",
            agent_context=(
                "[cost-coach] This request is large and underspecified. First propose a short plan "
                "(files to touch, steps, how you will verify) and wait for approval before editing."
            ),
        )
    return None


def check_prompt(text: str) -> List[Finding]:
    out = []
    for rule in (empty_prompt, vague_large, bundled_tasks):
        f = rule(text)
        if f:
            out.append(f)
            if f.rule == "empty_prompt":
                break
    return out


# ---- tool-level ---------------------------------------------------------------------------
def tool_call_budget(count: int, warn_at: int) -> Optional[Finding]:
    if count == warn_at:
        return Finding(
            rule="long_turn",
            billing_point="TURN",
            message=f"{count} tool calls in this turn, each re-sending the context. "
                    "Check whether the agent is going in circles.",
            agent_context=(
                f"[cost-coach] You have made {count} tool calls in this turn. Stop exploring: use the "
                "information you already have, finish the current step, and report status. Prefer "
                "one targeted search over many broad ones."
            ),
        )
    return None


def large_output(chars: int, limit: int, tool: str) -> Optional[Finding]:
    if chars > limit:
        return Finding(
            rule="large_tool_output",
            billing_point="CTX",
            message=f"{tool} output was {chars // 1000}K chars; it is re-read on every later call. "
                    "Ask for a narrower command or a line range.",
            agent_context=(
                f"[cost-coach] The last {tool} output was very large ({chars} chars). For further "
                "commands, narrow the output (filters, head/tail, --stat, line ranges, "
                "or codegraph queries) instead of dumping whole files/logs."
            ),
        )
    return None


# ---- repeats ------------------------------------------------------------------------------
def repeated_read(path: str, n: int, threshold: int) -> Optional[Finding]:
    if n == threshold:
        name = path.rsplit("/", 1)[-1]
        return Finding(
            rule="repeated_read", billing_point="CTX",
            message=f"{name} was read {n} times in this session. Each read adds the file to the "
                    "context again.",
            agent_context=f"[cost-coach] You already read {path}. Reuse what you read instead of reading it again.",
        )
    return None


def retry_loop(cmd: str, n: int, threshold: int) -> Optional[Finding]:
    if n == threshold:
        return Finding(
            rule="retry_loop", billing_point="TURN",
            message=f"Same command run {n} times: `{cmd[:50]}`. The agent may be retrying blindly.",
            agent_context="[cost-coach] You ran the same command several times. Stop, summarize what "
                          "failed, and change approach.",
        )
    return None


# ---- cache-related ------------------------------------------------------------------------
_CONFIG_FILES = ("claude.md", "agents.md", ".mcp.json", "settings.json", "settings.local.json",
                 "hooks.v1.json", ".devin/config.json")


def config_edit(path: str) -> Optional[Finding]:
    p = (path or "").lower().replace("\\", "/")
    if p and any(p.endswith(c) for c in _CONFIG_FILES):
        return Finding(
            rule="config_edit_midsession", billing_point="REBUILD",
            message=f"Agent is editing {path.rsplit('/', 1)[-1]} mid-session. Changing agent config "
                    "invalidates the cached prompt prefix; make such edits between sessions.",
        )
    return None


def cache_expired_resume(idle_s: float, cost: dict, cfg: dict) -> Optional[Finding]:
    """Prompt after an idle gap longer than the cache TTL, with a big context waiting to be re-written."""
    ctx = (cost or {}).get("last_context", 0)
    ttl = (cost or {}).get("ttl", cfg.get("cache_ttl_s", 300))
    if idle_s > ttl and ctx >= cfg.get("resume_context_tokens", 50000):
        mins = int(idle_s // 60)
        return Finding(
            rule="cache_expired_resume", billing_point="REBUILD",
            message=f"Idle {mins} min (> {ttl // 60} min cache), so the next turn re-writes "
                    f"~{ctx // 1000}K tokens at full write price. For a new task, start a new session "
                    "with a short summary.",
        )
    return None
