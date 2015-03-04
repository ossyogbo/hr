# -*- coding:utf-8 -*-
#
#
#    Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

from openerp import models, fields, api, exceptions, _


class hr_job(models.Model):

    _name = 'hr.job'
    _inherit = 'hr.job'

    max_employees = fields.Integer('Maximum Number of Employees')

    max_employees_fuzz = fields.Integer(
        'Expected Turnover',
        help="Recruitment module will allow you to \
        create this number of additional applicants and \
        contracts above the maximum value. Use this \
        number as a buffer to have additional \
        employees on hand to cover employee turnover.")

    # Do not write negative values for no. of recruitment
    @api.multi
    def write(self, vals):
        value = vals.get('no_of_recruitment', False)
        if value and value < 0:
            vals['no_of_recruitment'] = 0
        return super(hr_job, self).write(vals)


class hr_applicant(models.Model):

    _name = 'hr.applicant'
    _inherit = 'hr.applicant'

    @api.multi
    def create(self, vals):

        job_id = vals.get('job_id', False)
        if job_id:
            job = self.env['hr.job'].browse(job_id)
            if (job.state != 'recruit' and
                int(job.no_of_employee) >=
                    int(job.max_employees + job.max_employees_fuzz)):
                raise exceptions.except_orm(
                    _('Job not open for recruitment!'),
                    _('You may not register applicants for jobs that are not '
                      'recruiting.')
                )
        return super(hr_applicant, self).create(vals)


class hr_contract(models.Model):

    _name = 'hr.contract'
    _inherit = 'hr.contract'

    @api.model
    def _get_job_from_applicant(self):
        """If the applicant went through recruitment get the job id
        from there.
        """
        context = self.env.context
        res = False
        if context is not None:
            ee_ids = context.get('search_default_employee_id', False)
            if ee_ids and len(ee_ids) > 0:
                # If this is the first contract try to obtain job position from
                # application
                if len(self.search([('employee_id', 'in', ee_ids)])) > 0:
                    return res
                applicants = self.env['hr.applicant'].search(
                    [('emp_id', '=', ee_ids[0])])
                if len(applicants) > 0:
                    res = applicants[0].job_id
        return res

    # job_id = fields.Many2one('hr.job', 'Job', default=_get_job_from_applicant)
    # TODO Check if this is ok
    job_id = fields.Many2one(default=_get_job_from_applicant)

    @api.multi
    def create(self, vals):

        # If the contract is for an employee with a pre-existing contract for
        # the same job, then bypass checks.
        employee_id = vals.get('employee_id', False)
        if employee_id:
            contracts = self.search([
                ('employee_id', '=', employee_id),
                ('state', 'not in', ['draft', 'done']),
            ])
            for contract in contracts:
                if vals.get('job_id', False) == contract.job_id.id:
                    return super(hr_contract, self).create(vals)

        # 1. Verify job is in recruitment
        job_id = vals.get('job_id', False)
        if job_id:
            job = self.env['hr.job'].browse(job_id)
            if (job.state != 'recruit' and
                int(job.no_of_employee) >=
                    (int(job.max_employees) + job.max_employees_fuzz)):
                raise exceptions.except_orm(
                    _('The Job "%s" is not in recruitment!') % (job.name),
                    _('You may not create contracts for jobs that are not in '
                      'recruitment state.'))

        # 2. Verify that the number of open contracts < total expected
        # employees
        if job_id:
            contracts = self.search([
                ('job_id', '=', job_id),
                ('state', 'not in', ['done']),
            ])

            job = self.env['hr.job'].browse(job_id)
            expected_employees = job.expected_employees or 0
            max_employees = job.max_employees or 0
            max_employees_fuzz = job.max_employees_fuzz or 0

            if len(contracts) >= max(expected_employees,
                                     max_employees + max_employees_fuzz):
                raise exceptions.except_orm(
                    _('Maximum Number of Employees Exceeded!'),
                    _('The maximum number of employees for "%s" has been '
                      'exceeded.') % (job.name))
        return super(hr_contract, self).create(vals)


class hr_recruitment_request(models.Model):

    _name = 'hr.recruitment.request'
    _description = 'Request for recruitment of additional personnel'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    name = fields.Char('Description', size=64)
    user_id = fields.Many2one(
        'res.users',
        'Requesting User',
        required=True,
        default=lambda self: self.env.uid,
    )
    department_id = fields.Many2one(
        'hr.department',
        'Department',
    )
    job_id = fields.Many2one(
        'hr.job',
        'Job',
        required=True,
    )
    number = fields.Integer(
        'Number to Recruit', default=1)
    current_number = fields.Integer(
        compute='_no_of_employee',
        string="Current Number of Employees",
        readonly=True,
    )
    max_number = fields.Integer(
        related='job_id.max_employees',
        string="Maximum Number of Employees",
        readonly=True
    )
    reason = fields.Text(
        'Reason for Request',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirm', 'Confirmed'),
            ('exception', 'Exception'),
            ('recruitment', 'In Recruitment'),
            ('decline', 'Declined'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        'State',
        readonly=True,
    )
    _order = 'department_id, job_id'
    _track = {
        'state': {
            'hr_labour_recruitment.mt_alert_request_confirmed': (
                lambda s, cr, u, o, c=None: o['state'] == 'confirm'),
            'hr_labour_recruitment.mt_alert_request_exception': (
                lambda s, cr, u, o, c=None: o['state'] == 'exception'),
            'hr_labour_recruitment.mt_alert_request_approved': (
                lambda s, cr, u, o, c=None: o['state'] == 'recruitment'),
            'hr_labour_recruitment.mt_alert_request_declined': (
                lambda s, cr, u, o, c=None: o['state'] == 'decline'),
        },
    }

    @api.depends('job_id')
    def _no_of_employee(self):
        job = self.job_id
        if job:
            self.current_number = job.no_of_employee

    @api.onchange('job_id')
    def onchange_job(self):
        job = self.job_id
        if job:
            if job.department_id:
                self.department_id = job.department_id
            self.name = 'Personnel Request: ' + str(job.name)

    @api.multi
    def _needaction_domain_get(self):
        users_obj = self.env['res.users']
        domain = []
        has_prev_domain = False
        if users_obj.has_group('base.group_hr_manager'):
            domain = [('state', '=', 'recruitment')]
            has_prev_domain = True
        if users_obj.has_group('hr_security.group_hr_director'):
            if has_prev_domain:
                domain = ['|'] + domain
            domain = domain + [('state', 'in', ['confirm', 'exception'])]
        if len(domain) == 0:
            return False
        return domain

    @api.multi
    def condition_exception(self):
        for req in self:
            if (req.number + req.job_id.expected_employees >
                    req.job_id.max_employees):
                return True
        return False

    @api.multi
    def _state(self, state):
        for req in self:
            job = req.job_id
            if state == 'recruitment':
                job.write({'no_of_recruitment': req.number})
                job.set_recruit()
            elif state in ['done', 'cancel']:
                job.set_open()
            req.write({'state': state})
        return True

    @api.multi
    def _state_subscribe_users(self, state):
        imd_obj = self.env['ir.model.data']
        model, group1_id = imd_obj.get_object_reference(
            'base', 'group_hr_manager')
        model, group2_id = imd_obj.get_object_reference(
            'hr_security', 'group_hr_director')
        groups = self.env['res.groups'].browse([group1_id, group2_id])
        user_ids = list(set(groups[0].users.ids + groups[1].users.ids))
        self.message_subscribe_users(user_ids=user_ids)
        return self._state(state)

    @api.multi
    def state_confirm(self):
        return self._state_subscribe_users('confirm')

    @api.multi
    def state_exception(self):
        return self._state_subscribe_users('exception')

    @api.multi
    def state_recruitment(self):
        return self._state_subscribe_users('recruitment')

    @api.multi
    def state_done(self, cr, uid, ids, context=None):
        return self._state('done')

    @api.multi
    def state_cancel(self):
        return self._state('cancel')
