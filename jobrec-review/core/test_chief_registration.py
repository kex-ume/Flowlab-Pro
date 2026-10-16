from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Role, Personnel
from .personnel_records import flags, assignable_roles


class ChiefRegistrationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('chief-registration-test',password='Chief-Test-Only-529!')
        self.role=Role.objects.get(name='Chief Metrologist')
        Personnel.objects.create(user=self.user,name='Chief Test',role=self.role,qualifications='',years_of_experience=0)
        self.client.force_login(self.user)

    def test_chief_has_explicit_role_based_officer_authority(self):
        self.assertTrue(flags(self.user)['may_manage'])
        for permission in ('may_authorize','may_assess','may_verify'):
            self.assertTrue(flags(self.user)[permission])
        self.assertEqual(self.client.get(reverse('personnel_create')).status_code,200)
        page=self.client.get(reverse('dashboard'))
        self.assertNotContains(page,'href="/settings/records"')
        self.assertContains(page,'Retained Records &amp; Audit')

    def test_chief_cannot_appoint_administrator(self):
        self.assertFalse(assignable_roles(self.user).filter(name='Administrator').exists())
        data=dict(name='Forbidden Appointment',role=Role.objects.get(name='Administrator').pk,qualifications='Test',years_of_experience=1,
            employment_status='active',login_username='forbidden-admin',temporary_password='Secure-Test-Choice-952!')
        response=self.client.post(reverse('personnel_create'),data)
        self.assertEqual(response.status_code,200)
        self.assertFalse(User.objects.filter(username='forbidden-admin').exists())

    def test_chief_registers_independent_ei_personnel(self):
        role=assignable_roles(self.user).first()
        self.assertIsNotNone(role)
        data=dict(name='Registered Person',role=role.pk,qualifications='Unverified degree',years_of_experience=2,
            employment_status='active',login_username='chief-added-person',temporary_password='Secure-Test-Choice-952!')
        response=self.client.post(reverse('personnel_create'),data)
        self.assertEqual(response.status_code,302)
        person=Personnel.objects.get(user__username='chief-added-person')
        self.assertFalse(person.authorizations.exists())
        self.assertEqual(person.profile_history.count(),1)
