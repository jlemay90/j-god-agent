import unittest
from unittest.mock import patch
import j_repository as repo


def fake_git(*args):
    if args == ('remote','get-url','origin'):
        return 'https://github.com/jlemay90/j-god-agent.git'
    if args[:1] == ('ls-tree',): return 'j_retrieval.py\nmaster_directive.md\n.env\n'
    if args[:1] == ('rev-parse',): return 'a'*40
    if args[:1] == ('diff',): return ''
    if args == ('show','HEAD:j_retrieval.py'): return 'line one\nline two\nline three'
    if args == ('fetch','--no-tags','origin','main'): return ''
    raise AssertionError(args)


class RepositoryTests(unittest.TestCase):
    @patch.object(repo,'git',side_effect=fake_git)
    def test_source_read_has_commit_and_range(self, mocked):
        result=repo.run('read j_retrieval.py 2 1')
        self.assertIn('2: line two',result)
        self.assertNotIn('line three',result)
        self.assertIn('a'*12,result)

    @patch.object(repo,'git',side_effect=fake_git)
    def test_private_files_and_traversal_rejected(self, mocked):
        for name in ['.env','master_directive.md','../j_retrieval.py','private_backups/code.py']:
            with self.assertRaises(repo.RepoError): repo.run('read '+name)

    @patch.object(repo,'git',side_effect=fake_git)
    def test_arbitrary_git_and_shell_not_available(self, mocked):
        for action in ['push origin main','status; echo hello','read j_retrieval.py 1 999','read j_retrieval.py -1 2']:
            with self.assertRaises(repo.RepoError): repo.run(action)

    @patch.object(repo,'git',return_value='https://github.com/other/repo.git')
    def test_other_repository_rejected(self, mocked):
        with self.assertRaises(repo.RepoError): repo.run('status')

    @patch.object(repo,'git',return_value='https://github.com.evil.example/jlemay90/j-god-agent.git')
    def test_lookalike_host_rejected(self, mocked):
        with self.assertRaises(repo.RepoError): repo.run('files')

    @patch.object(repo,'git',side_effect=fake_git)
    def test_sync_only_fetches_approved_main(self, mocked):
        self.assertIn('fetch succeeded',repo.run('sync'))
        calls=[c.args for c in mocked.call_args_list]
        self.assertIn(('fetch','--no-tags','origin','main'),calls)
        self.assertFalse(any(c[0] in ('pull','push','merge','reset') for c in calls))

    @patch.object(repo,'git',side_effect=lambda *a: ('sk-'+'x'*30) if a[0]=='show' else fake_git(*a))
    def test_credential_like_source_withheld(self,mocked):
        with self.assertRaises(repo.RepoError): repo.run('read j_retrieval.py')


if __name__=='__main__':unittest.main()
