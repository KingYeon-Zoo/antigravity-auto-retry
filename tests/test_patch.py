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


def inline_object(p):
    message = ('"This error is likely temporary. Please wait."' if p.case_name == 'retryable' else
               'view(Fragment,{children:["You can prompt the model to try again or start a new conversation if the error persists."]})')
    return ('{id:m,icon:b,title:title,message:'+message+',primaryAction:{label:"'+p.primary_label+
            '",onClick:()=>{send([new Message({chunk:{case:"text",value:"'+p.primary_message+
            '"}})])}},secondaryAction:{label:"Copy debug info",onClick:()=>{copy(`Trajectory ID: ${o}\nError: ${r.fullError||r.shortError}`)}}}')


class InlineVersionTests(unittest.TestCase):
    def test_inline_idempotence_and_backup_restore(self):
        text='function notice(retryable){return retryable?'+inline_object(patcher.CASE_PATCHES[0])+':'+inline_object(patcher.CASE_PATCHES[1])+'}'
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'bundle.js';f.write_text(text)
            self.assertTrue(patcher.patch_file(f));changed=f.read_text()
            self.assertTrue(patcher.patch_file(f));self.assertEqual(f.read_text(),changed)
            self.assertTrue(patcher.restore_file(f));self.assertEqual(f.read_text(),text)

    def test_retry_once_per_notification_and_preserve_actions(self):
        import subprocess
        for p in patcher.CASE_PATCHES:
            updated,changed,_=patcher.apply_case_patch(inline_object(p),p)
            self.assertTrue(changed)
            js='''const assert=require('node:assert/strict');let m='id1',b=0,title='测试',o='trajectory',r={shortError:'错误'},sent=[],copied=[];
            const Message=function(x){this.value=x.chunk.value};const send=x=>sent.push(x[0].value);const copy=x=>copied.push(x);
            const view=(_,x)=>x,Fragment=0;globalThis.setTimeout=fn=>{fn();return 1};
            function notice(){return '''+updated+'''}
            assert.equal(notice(),undefined);assert.equal(sent.length,1);
            const second=notice();assert.equal(sent.length,1);second.secondaryAction.onClick();assert.equal(copied.length,1);
            second.primaryAction.onClick();assert.equal(sent.length,2);
            m='id2';assert.equal(notice(),undefined);assert.equal(sent.length,3);
            '''
            subprocess.run(['node','-e',js],check=True,capture_output=True)

    def test_mixed_and_duplicate_signatures_rejected(self):
        for p in patcher.CASE_PATCHES:
            for text in [sample()+inline_object(p),inline_object(p)*2]:
                updated,changed,_=patcher.apply_case_patch(text,p)
                self.assertFalse(changed);self.assertEqual(updated,text)


if __name__ == '__main__':
    unittest.main()
