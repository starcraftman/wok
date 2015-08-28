""" All tests related to tasks. """
from __future__ import absolute_import, print_function

import glob
import logging
import mock
import os
import pytest
import sys

from pakit.exc import PakitError, PakitCmdError, PakitLinkError
from pakit.main import global_init
from pakit.recipe import RecipeDB
from pakit.shell import Command
from pakit.task import (
    subseq_match, substring_match, walk_and_link, walk_and_unlink,
    Task, RecipeTask, InstallTask, RemoveTask, UpdateTask, DisplayTask,
    ListInstalled, ListAvailable, SearchTask
)
import pakit.task

def teardown_module(module):
    try:
        config_file = os.path.join(os.path.dirname(__file__), 'pakit.yaml')
        config = global_init(config_file)
        tmp_dir = os.path.dirname(config.get('paths.prefix'))
        cmd = Command('rm -rf ' + tmp_dir)
        cmd.wait()
    except PakitError:
        logging.error('Could not clean ' + tmp_dir)

def test_subseq_match():
    haystack = 'Hello World!'
    assert subseq_match(haystack, 'hwor')
    assert subseq_match(haystack, 'HeWd')
    assert not subseq_match(haystack, 'Good')

def test_substring_match():
    haystack = 'Hello World!'
    assert substring_match(haystack, 'hello')
    assert substring_match(haystack, 'Hello')
    assert not substring_match(haystack, 'HelloW')

class TestLinking(object):
    def setup(self):
        config_file = os.path.join(os.path.dirname(__file__), 'pakit.yaml')
        config = global_init(config_file)
        self.src = config.get('paths.prefix')
        self.dst = config.get('paths.link')
        self.teardown()

        self.subdir = os.path.join(self.src, 'subdir')
        os.makedirs(self.subdir)
        os.makedirs(self.dst)

        self.fnames = [os.path.join(self.src, 'file' + str(num)) for num in range(0, 6)]
        self.fnames += [os.path.join(self.subdir, 'file' + str(num)) for num in range(0, 4)]
        self.dst_fnames = [fname.replace(self.src, self.dst) for fname in self.fnames]
        for fname in self.fnames:
            with open(fname, 'wb') as fout:
                fout.write('dummy'.encode())

    def teardown(self):
        try:
            cmd = Command('rm -rf ' + os.path.dirname(self.src))
            cmd.wait()
        except PakitError:
            logging.error('Could not clean ' + self.src)

    def test_walk_and_link_works(self):
        walk_and_link(self.src, self.dst)
        for fname in self.dst_fnames:
            assert os.path.islink(fname)
            assert os.readlink(fname) == fname.replace(self.dst, self.src)

    def test_walk_and_link_raises(self):
        walk_and_link(self.src, self.dst)
        with pytest.raises(PakitLinkError):
            walk_and_link(self.src, self.dst)

    def test_walk_and_unlink(self):
        walk_and_link(self.src, self.dst)
        walk_and_unlink(self.src, self.dst)
        for fname in self.dst_fnames:
            assert not os.path.exists(fname)
        assert not os.path.exists(self.subdir.replace(self.src, self.dst))
        for fname in self.fnames:
            assert os.path.exists(fname)

    def test_walk_and_unlink_missing(self):
        walk_and_link(self.src, self.dst)
        os.remove(self.dst_fnames[0])
        walk_and_unlink(self.src, self.dst)
        for fname in self.dst_fnames:
            assert not os.path.exists(fname)
        assert not os.path.exists(self.subdir.replace(self.src, self.dst))
        for fname in self.fnames:
            assert os.path.exists(fname)

class TestTaskBase(object):
    """ Shared setup, most task tests will want this. """
    def setup(self):
        config_file = os.path.join(os.path.dirname(__file__), 'pakit.yaml')
        self.config = global_init(config_file)
        self.rdb = RecipeDB()
        self.recipe = self.rdb.get('ag')

    def teardown(self):
        RemoveTask(self.recipe).run()
        try:
            os.remove(os.path.join(os.path.dirname(self.recipe.install_dir), 'installed.yaml'))
        except OSError:
            pass
        try:
            self.recipe.repo.clean()
        except PakitCmdError:
            pass

class DummyTask(Task):
    def run(self):
        pass

class TestTask(TestTaskBase):
    def test__str__(self):
        expect = 'DummyTask: Config File ' + self.config.filename
        task = DummyTask()
        print(task)
        assert str(task) == expect

class TestTaskRecipe(TestTaskBase):
    def test_recipe_str(self):
        assert RecipeTask(self.recipe).recipe is self.recipe

    def test_recipe_object(self):
        assert RecipeTask(self.recipe).recipe is self.recipe

    def test__eq__(self):
        assert InstallTask('ag') == InstallTask('ag')
        assert RemoveTask('ag') != InstallTask('ag')
        assert InstallTask('ag') != InstallTask('vim')

    def test__str__(self):
        expect = 'RecipeTask: ag           Grep like tool optimized for speed'
        task = RecipeTask(self.recipe)
        print(task)
        assert expect == str(task)

class TestTaskInstall(TestTaskBase):
    def test_is_not_installed(self):
        task = InstallTask(self.recipe)
        task.run()
        name = self.recipe.name
        build_bin = os.path.join(task.path('prefix'), name, 'bin', name)
        link_bin = os.path.join(task.path('link'), 'bin', name)
        assert os.path.exists(build_bin)
        assert os.path.exists(link_bin)
        assert os.path.realpath(link_bin) == build_bin

    @mock.patch('pakit.task.logging')
    def test_is_installed(self, mock_log):
        task = InstallTask(self.recipe)
        task.run()
        task.run()
        assert mock_log.error.called is True

class TestTaskRollback(object):
    def setup(self):
        config_file = os.path.join(os.path.dirname(__file__), 'pakit.yaml')
        self.config = global_init(config_file)
        self.recipe = None

    def teardown(self):
        try:
            Command('rm -rf ' + self.recipe.install_dir).wait()
        except PakitCmdError:
            pass
        try:
            Command('rm -rf ' + self.recipe.link_dir).wait()
        except PakitCmdError:
            pass
        try:
            self.recipe.repo.clean()
        except PakitCmdError:
            pass

    def _get_recipe(self, name):
        """ Helper for now, RecipeDB needs work """
        mod = __import__('tests.formula.{cls}'.format(cls=name))
        mod = getattr(mod, 'formula')
        mod = getattr(mod, name)
        cls = getattr(mod, name.capitalize())
        obj = cls()
        obj.set_config(self.config)
        return obj

    def test_install_build_error(self):
        self.recipe = self._get_recipe('build')
        with pytest.raises(PakitCmdError):
            InstallTask(self.recipe).run()
        assert os.listdir(os.path.dirname(self.recipe.install_dir)) == []
        assert os.listdir(os.path.dirname(self.recipe.source_dir)) == []

    def test_install_link_error(self):
        self.recipe = self._get_recipe('link')
        with pytest.raises(PakitLinkError):
            InstallTask(self.recipe).run()
        assert os.listdir(os.path.dirname(self.recipe.install_dir)) == []
        assert os.listdir(os.path.dirname(self.recipe.source_dir)) == []
        assert not os.path.exists(self.recipe.link_dir)

    def test_install_verify_error(self):
        self.recipe = self._get_recipe('verify')
        with pytest.raises(AssertionError):
            InstallTask(self.recipe).run()
        assert os.listdir(os.path.dirname(self.recipe.install_dir)) == []
        assert os.listdir(os.path.dirname(self.recipe.source_dir)) == []
        assert not os.path.exists(self.recipe.link_dir)

class TestTaskRemove(TestTaskBase):
    @mock.patch('pakit.task.logging')
    def test_is_not_installed(self, mock_log):
        task = RemoveTask(self.recipe)
        task.run()
        mock_log.error.assert_called_with('Not Installed: ag')

    def test_is_installed(self):
        InstallTask(self.recipe).run()
        task = RemoveTask(self.recipe)
        task.run()

        assert os.path.exists(task.path('prefix'))
        globbed = glob.glob(os.path.join(task.path('prefix'), '*'))
        assert globbed == [os.path.join(task.path('prefix'), 'installed.yaml')]
        assert not os.path.exists(task.path('link'))

class TestTaskUpdate(TestTaskBase):
    def test_is_current(self):
        recipe = self.recipe
        InstallTask(recipe).run()
        assert pakit.task.IDB.get(recipe.name)['hash'] == recipe.repo.cur_hash
        first_hash = recipe.repo.cur_hash

        UpdateTask(recipe).run()
        assert pakit.task.IDB.get(recipe.name)['hash'] == recipe.repo.cur_hash
        assert first_hash == recipe.repo.cur_hash

    def test_is_not_current(self):
        recipe = self.recipe
        old_repo_name = recipe.repo_name

        recipe.repo = 'stable'
        InstallTask(recipe).run()
        expect = 'c81622c5c5313c05eab2da3b5eca6c118b74369e'
        assert pakit.task.IDB.get(recipe.name)['hash'] == expect
        # assert pakit.task.IDB.get(recipe.name)['hash'] == recipe.repo.cur_hash

        recipe.repo = 'unstable'
        UpdateTask(recipe).run()
        assert pakit.task.IDB.get(recipe.name)['hash'] != expect

        recipe.repo = old_repo_name

    def test_save_old_install(self):
        recipe = self.recipe
        InstallTask(recipe).run()
        task = UpdateTask(recipe)
        task.save_old_install()
        assert pakit.task.IDB.get(recipe.name) is None
        assert not os.path.exists(recipe.install_dir)
        assert os.path.exists(recipe.install_dir + '_bak')

    def test_restore_old_install(self):
        recipe = self.recipe
        InstallTask(recipe).run()
        task = UpdateTask(recipe)
        task.save_old_install()
        task.restore_old_install()
        assert pakit.task.IDB.get(recipe.name)['hash'] == recipe.repo.cur_hash
        assert os.path.exists(recipe.install_dir)
        assert not os.path.exists(recipe.install_dir + '_bak')
        recipe.verify()

class TestTaskQuery(TestTaskBase):
    def test_list_installed(self):
        InstallTask(self.recipe).run()
        task = ListInstalled()
        out = task.run().split('\n')
        assert len(out) == 3
        assert out[-1].find('  ' + self.recipe.name) == 0

    def test_list_available(self):
        task = ListAvailable()
        out = task.run().split('\n')
        expect = ['  ' + line for line in RecipeDB().names(desc=True)]
        print(expect)
        print(out)
        assert out[0] == 'Available Recipes:'
        assert out[2:] == expect

    def test_search_names(self):
        results = SearchTask(RecipeDB().names(), ['vim']).run()
        assert results[1:] == ['vim']

    def test_search_desc(self):
        results = SearchTask(RecipeDB().names(desc=True), ['grep']).run()
        assert results[1:] == [str(self.recipe)]

    def test_display_info(self):
        results = DisplayTask(self.recipe).run()
        assert results == self.recipe.info()
