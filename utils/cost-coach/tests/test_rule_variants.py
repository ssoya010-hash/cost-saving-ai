"""Phrasing variants: rules must catch reworded anti-patterns and not flag real instructions.

The rules combine word lists with structure (prompt length, word count, and content signals such
as file names, code, identifiers and action verbs), so small rewording does not slip through.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coach import rules  # noqa: E402

EMPTY = ["ㅇㅇ", "ㅇㅇㅇ", "ㅇㅇ 진행시켜", "계속 부탁해", "계속해 주세요", "네 그렇게 해주세요", "좋아요 진행해주세요",
         "오키", "ㅇㅋ요", "넵넵", "yes please", "ok go", "sounds good, proceed", "👍", "go for it",
         "keep going", "ㄱㄱ씽", "gogo", "ㅇㅋ 부탁드려요", "오 좋네요"]
NOT_EMPTY = ["ok, now add tests for parse_date in utils/date.py",
             "Continue but skip the migration step and run pytest", "계속 진행하되 src/a.py는 건드리지 마",
             "yes, and also update README.md", "네 그리고 테스트도 추가해줘", "fix login.ts", "why?",
             "run pytest", "배포해줘", "PR #42 봐줘", "refactor auth", "use pnpm"]
CORRECTION = ["아니 그게 아니라", "그거 말고 다른 방식으로", "아닌데?", "이상하게 고쳤네 원래대로", "다시",
              "방금 거 취소", "not quite, use ISO", "Hmm that's wrong", "actually no, keep the old one",
              "that broke the build", "still failing", "왜 테스트를 지웠어?"]
NOT_CORRECTION = ["no need to change the tests, just fix parse()", "stop the dev server and run pytest in tests/",
                  "Undo button should be disabled when list is empty in ui/list.tsx",
                  "wrong answer is returned by calc() in math.py, fix it",
                  "Nobody calls this function anymore; remove it", "Add a stop() method to the worker",
                  "다시 한번 설명해줘 이 함수 구조", "취소 버튼 추가해줘 in modal.tsx",
                  "Rollback script for db migrations, please write one", "이상한 로그가 있는지 확인해줘 in app.log"]


class VariantTests(unittest.TestCase):
    def check(self, items, fn, want):
        wrong = [t for t in items if bool(fn(t)) != want]
        self.assertEqual(wrong, [], f"{len(wrong)}/{len(items)} wrong")

    def test_empty_variants_caught(self):
        self.check(EMPTY, rules.empty_prompt, True)

    def test_real_instructions_not_empty(self):
        self.check(NOT_EMPTY, rules.empty_prompt, False)

    def test_correction_variants_caught(self):
        self.check(CORRECTION, rules.is_correction, True)

    def test_requests_not_corrections(self):
        self.check(NOT_CORRECTION, rules.is_correction, False)


if __name__ == "__main__":
    unittest.main()
