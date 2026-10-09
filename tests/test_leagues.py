from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from fantasy.models import FantasyTeam
from leagues.models import JOIN_CODE_ALPHABET, League, LeagueMember, unique_join_code


class LeagueTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user('alice', password='pass12345')
        self.bob = User.objects.create_user('bob', password='pass12345')

    def make_league(self):
        team = FantasyTeam.objects.create(user=self.alice, name='Alice FC')
        league = League.objects.create(name='Test League', admin=self.alice)
        LeagueMember.objects.create(league=league, team=team)
        return league

    def test_join_codes_are_six_safe_characters(self):
        code = unique_join_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(all(c in JOIN_CODE_ALPHABET for c in code))

    def test_creating_a_league_adds_the_creator(self):
        self.client.login(username='alice', password='pass12345')
        response = self.client.post(reverse('leagues:create'), {'name': 'Office League'})
        league = League.objects.get(name='Office League')
        self.assertRedirects(
            response, reverse('leagues:detail', args=[league.pk]), fetch_redirect_response=False
        )
        self.assertEqual(league.admin, self.alice)
        self.assertEqual(league.members.count(), 1)

    def test_empty_name_is_rejected(self):
        self.client.login(username='alice', password='pass12345')
        self.client.post(reverse('leagues:create'), {'name': '   '})
        self.assertEqual(League.objects.count(), 0)

    def test_joining_with_a_code_ignores_case(self):
        league = self.make_league()
        self.client.login(username='bob', password='pass12345')
        self.client.post(reverse('leagues:join'), {'code': league.join_code.lower()})
        self.assertEqual(league.members.count(), 2)

    def test_joining_twice_does_not_duplicate(self):
        league = self.make_league()
        self.client.login(username='bob', password='pass12345')
        self.client.post(reverse('leagues:join'), {'code': league.join_code})
        self.client.post(reverse('leagues:join'), {'code': league.join_code})
        self.assertEqual(league.members.count(), 2)

    def test_wrong_code_is_rejected(self):
        league = self.make_league()
        self.client.login(username='bob', password='pass12345')
        self.client.post(reverse('leagues:join'), {'code': 'ZZZZZZ'})
        self.assertEqual(league.members.count(), 1)

    def test_non_members_cannot_view_a_league(self):
        league = self.make_league()
        self.client.login(username='bob', password='pass12345')
        response = self.client.get(reverse('leagues:detail', args=[league.pk]))
        self.assertEqual(response.status_code, 404)

    def test_members_can_leave_but_the_admin_cannot(self):
        league = self.make_league()
        self.client.login(username='bob', password='pass12345')
        self.client.post(reverse('leagues:join'), {'code': league.join_code})
        self.client.post(reverse('leagues:leave', args=[league.pk]))
        self.assertEqual(league.members.count(), 1)

        self.client.login(username='alice', password='pass12345')
        self.client.post(reverse('leagues:leave', args=[league.pk]))
        self.assertEqual(league.members.count(), 1)

    def test_only_the_admin_can_delete(self):
        league = self.make_league()
        self.client.login(username='bob', password='pass12345')
        self.client.post(reverse('leagues:delete', args=[league.pk]))
        self.assertTrue(League.objects.filter(pk=league.pk).exists())

        self.client.login(username='alice', password='pass12345')
        self.client.post(reverse('leagues:delete', args=[league.pk]))
        self.assertFalse(League.objects.filter(pk=league.pk).exists())