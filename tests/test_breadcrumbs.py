"""Breadcrumb navigation never mutates data or invents a parent action URL."""
import unittest
from app.navigation import flow_breadcrumbs, ei_breadcrumbs


class BreadcrumbTests(unittest.TestCase):
    def assert_valid(self, rows):
        self.assertEqual(sum(row['current'] for row in rows),1)
        self.assertTrue(rows[-1]['current'])
        self.assertTrue(all(row['url'].startswith('/') and not row['url'].startswith('//') for row in rows))
        self.assertTrue(all(row['label'] for row in rows))

    def test_job_edit_links_to_its_own_job(self):
        rows=flow_breadcrumbs('/projects/jobs/18/edit',title='Edit Job')
        self.assert_valid(rows)
        self.assertEqual([x['url'] for x in rows],['/dashboard','/projects/jobs','/projects/jobs/18','/projects/jobs/18/edit'])

    def test_project_jobs_use_authorized_rendered_project_label(self):
        rows=flow_breadcrumbs('/projects/jobs',{'project':'3'},'Projects',(3,'PRJ-EATL-003'))
        self.assert_valid(rows)
        self.assertEqual(rows[-1]['label'],'PRJ-EATL-003')
        self.assertEqual(rows[-1]['url'],'/projects/jobs?project=3')

    def test_user_management_is_under_settings_only(self):
        rows=flow_breadcrumbs('/settings/users',title='User Management')
        self.assertEqual([x['label'] for x in rows],['FlowLab Pro','Settings','User Management'])
        self.assert_valid(rows)

    def test_workspace_parent_uses_real_workspace_route(self):
        rows=flow_breadcrumbs('/workspace/database/audit-trail',title='Audit Trail',workspace_titles={'database':'Database & Records'})
        self.assertEqual(rows[1]['url'],'/workspace/database')
        self.assertEqual(rows[1]['label'],'Database & Records')
        self.assert_valid(rows)

    def test_uncertainty_records_link_back_to_uncertainty_module(self):
        rows=flow_breadcrumbs('/uncertainty',{'view':'records'},'Uncertainty Management')
        self.assertEqual(rows[-2]['url'],'/uncertainty')
        self.assertEqual(rows[-1]['label'],'Calculation Records')
        self.assert_valid(rows)

    def test_ei_personnel_record_path(self):
        rows=ei_breadcrumbs('/ei-lab/personnel/4/competency/','/ei-lab/','ei_personnel_workspace')
        self.assertEqual([x['label'] for x in rows],['E&I Lab','Records','Personnel','Personnel Record'])
        self.assertEqual(rows[2]['url'],'/ei-lab/personnel/')
        self.assert_valid(rows)

    def test_ei_scope_budget_parent_is_existing_scope_register(self):
        rows=ei_breadcrumbs('/ei-lab/settings/scopes/2/uncertainty-budget/','/ei-lab/','scope_uncertainty_budget')
        self.assertEqual(rows[-2]['url'],'/ei-lab/settings/scopes/')
        self.assertEqual(rows[-1]['label'],'Uncertainty Budget')
        self.assert_valid(rows)

    def test_ei_standalone_prefix_and_filtered_register(self):
        rows=ei_breadcrumbs('/personnel/','/','personnel_list',{'search':'A & B'})
        self.assertEqual(rows[-1]['url'],'/personnel/?search=A+%26+B')
        self.assertEqual([x['label'] for x in rows],['E&I Lab','Records','Personnel'])
        self.assert_valid(rows)

    def test_all_major_module_parents_remain_local_get_pages(self):
        for path in ('/settings','/equipment/3/edit','/programme','/iso17025/clause-checklist/6/personnel','/documents','/capa/3','/tools/generate-cover','/recycle-bin'):
            with self.subTest(path=path): self.assert_valid(flow_breadcrumbs(path,title='Page'))
        for path in ('/jobs/new/','/equipment/3/','/environment/new/','/waybills/incoming/3/','/procedures/3/edit/','/profile/edit/','/capa/3/'):
            with self.subTest(path=path): self.assert_valid(ei_breadcrumbs('/ei-lab'+path,'/ei-lab/','detail'))


if __name__=='__main__': unittest.main()
