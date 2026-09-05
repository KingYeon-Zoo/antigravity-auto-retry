"""使用合成 JS 和临时文件验证补丁，不接触本机应用。"""
import tempfile
import unittest
from pathlib import Path
import patch_antigravity as patcher


def sample():
    return ''.join(
        f'case"{p.case_name}":return{{id:x,message:"test",primaryAction:a("{p.primary_label}","{p.primary_message}"),secondaryAction:b()}}'
        for p in patcher.CASE_PATCHES
    )


class PatchTests(unittest.TestCase):
    def test_supported_cases_and_idempotence(self):
        text = sample()
        for patch in patcher.CASE_PATCHES:
            updated, changed, _ = patcher.apply_case_patch(text, patch)
            self.assertTrue(changed)
            again, changed_again, _ = patcher.apply_case_patch(updated, patch)
            self.assertFalse(changed_again)
            self.assertEqual(updated, again)
            text = updated

    def test_unknown_structure_unchanged(self):
        text = 'unknown bundle'
        for patch in patcher.CASE_PATCHES:
            updated, changed, _ = patcher.apply_case_patch(text, patch)
            self.assertFalse(changed)
            self.assertEqual(text, updated)

    def test_ambiguous_match_unchanged(self):
        text = sample() * 2
        for patch in patcher.CASE_PATCHES:
            updated, changed, _ = patcher.apply_case_patch(text, patch)
            self.assertFalse(changed)
            self.assertEqual(text, updated)

    def test_backup_restore_and_incomplete_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'bundle.js'
            original = sample()
            target.write_text(original, encoding='utf-8')
            self.assertTrue(patcher.patch_file(target))
            self.assertNotEqual(target.read_text(), original)
            self.assertTrue(patcher.restore_file(target))
            self.assertEqual(target.read_text(), original)
            incomplete = original.replace('case"generic"', 'case"different"')
            target.write_text(incomplete, encoding='utf-8')
            self.assertFalse(patcher.patch_file(target))
            self.assertEqual(target.read_text(), incomplete)


if __name__ == '__main__':
    unittest.main()
