import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command as run_command
from django.core.management.base import CommandError
from django.test import TestCase

from players.management.commands.prepare_site import Command as PrepareSite

ADMIN_ENV = {
    'DJANGO_SUPERUSER_USERNAME': 'boss',
    'DJANGO_SUPERUSER_PASSWORD': 'a-long-test-password',
    'DJANGO_SUPERUSER_EMAIL': 'boss@example.com',
}


class PrepareSiteTests(TestCase):
    def test_creates_the_admin_once(self):
        with mock.patch.dict(os.environ, ADMIN_ENV):
            PrepareSite().create_admin()
            PrepareSite().create_admin()
        users = get_user_model().objects.filter(username='boss')
        self.assertEqual(users.count(), 1)
        self.assertTrue(users.first().is_superuser)

    def test_does_nothing_without_the_admin_variables(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            PrepareSite().create_admin()
        self.assertFalse(get_user_model().objects.exists())


class RefreshDataTests(TestCase):
    @mock.patch('players.management.commands.refresh_data.call_command')
    def test_keeps_going_after_a_failed_step(self, fake_call):
        def fail_on_stats(name, *args, **kwargs):
            if name == 'import_stats':
                raise CommandError('no stats yet')

        fake_call.side_effect = fail_on_stats
        run_command('refresh_data')
        steps = [call.args[0] for call in fake_call.call_args_list]
        self.assertEqual(steps, ['import_data', 'import_stats', 'update_points'])