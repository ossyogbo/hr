# -*- coding:utf-8 -*-
#
#
#    Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
#    Copyright (c) 2005-2006 Axelor SARL. (http://www.axelor.com)
#    and 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from datetime import datetime, timedelta
from pytz import timezone, utc

from openerp import models, fields, api, exceptions, _


class hr_holidays_status(models.Model):

    _inherit = 'hr.holidays.status'

    ex_rest_days = fields.Boolean(
        'Exclude Rest Days',
        help="If enabled, the employee's day off  is skipped "
             "in leave days calculation.",
    )

    ex_public_holidays = fields.Boolean(
        'Exclude Public Holidays',
        help="If enabled, public holidays are skipped in leave days "
             "calculation.",
    )


class hr_holidays(models.Model):

    _name = 'hr.holidays'
    _inherit = ['hr.holidays', 'ir.needaction_mixin']

    real_days = fields.Float('Total Days', digits=(16, 1),
                             compute='_compute_days')
    rest_days = fields.Float('Rest Days', digits=(16, 1),
                             compute='_compute_days')
    public_holiday_days = fields.Float('Public Holidays',
                                       digits=(16, 1),
                                       compute='_compute_days')
    return_date = fields.Char('Return Date', size=32,
                              compute='_compute_days')

    _skip_compute_days = False

    @api.model
    def _employee_get(self):

        context, uid = self.env.context, self.env.user.id

        # If the user didn't enter from "My Leaves"
        # don't pre-populate Employee field
        import logging
        _l = logging.getLogger(__name__)
        _l.warning('context: %s', context)
        if not context.get('search_default_my_leaves', False):
            return False

        employees = self.env['hr.employee'].search([('user_id',
                                                     '=',
                                                     uid)])

        return employees and employees[0].id or False

    @api.model
    def _days_get(self):

        context = self.env.context

        date_from = context.get('default_date_from')
        date_to = context.get('default_date_to')
        if date_from and date_to:
            delta = fields.Datetime.from_string(date_to) - \
                fields.Datetime.from_string(date_from)
            return delta.days or 1
        return False

    _defaults = {
        'employee_id': _employee_get,
        'number_of_days_temp': _days_get,
    }

    _order = 'date_from asc, type desc'

    @api.multi
    @api.constrains('number_of_days_temp')
    def _check_number_of_days_temp(self):
        for leave in self:
            if leave.number_of_days_temp == 0.0:
                raise exceptions.Warning(
                    _('Warning'),
                    _('You cannot save leave with no days')
                )

    @api.model
    def _needaction_domain_get(self):

        context, uid = self.env.context, self.env.user.id
        users_obj = self.env['res.users']
        domain = []

        if users_obj.has_group('base.group_hr_manager'):
            domain = [('state', 'in', ['draft', 'confirm'])]
            return domain

        elif users_obj.has_group(
                'hr_holidays_extension.group_hr_leave'):
            domain = [('state', 'in', ['confirm']), (
                'employee_id.user_id', '!=', uid)]
            return domain

        return False

    @api.multi
    @api.depends('number_of_days_temp', 'date_from',
                 'date_to', 'holiday_status_id', 'employee_id')
    def _compute_days(self):
        self._skip_compute_days = True
        self.sudo()
        for leave in self:
            holiday_obj = leave.env['hr.holidays.public']
            sched_detail_obj = leave.env['hr.schedule.detail']

            def _date_localize(d, index1, index2, h, m, s):
                dt = utc.localize(fields.Datetime.from_string(d))
                dt = dt.astimezone(local_tz)
                dt = dt.replace(hour=h, minute=m, second=s)
                times = sched_detail_obj.scheduled_begin_end_times(
                    leave.employee_id.id,
                    leave.employee_id.contract_id.id, dt)
                if len(times) > 0:
                    return times[index1][index2]
                else:
                    return dt

            if leave.env.user and leave.env.user.tz:
                local_tz = timezone(leave.env.user.tz)
            else:
                local_tz = timezone('Africa/Addis_Ababa')

            if leave.date_from:
                dt_from = _date_localize(leave.date_from, 0, 0,
                                         0, 0, 0)
                leave.date_from = dt_from.astimezone(utc)
                next_dt = dt_from
            if leave.date_to:
                dt_to = _date_localize(leave.date_to, -1, 1,
                                       23, 59, 59)
                leave.date_to = dt_to.astimezone(utc)
                if self.date_from and self.number_of_days_temp:
                    self.number_of_days_temp = 0
                next_dt = dt_to

            if ((not leave.date_from and not leave.number_of_days_temp) or
                    (not leave.date_from and not leave.date_to) or
                    (not leave.date_to and not leave.number_of_days_temp)):
                leave.real_days = 0
                leave.public_holiday_days = 0
                leave.rest_days = 0
                leave.return_date = ''
                return

            ex_rd = leave.holiday_status_id.ex_rest_days
            ex_ph = leave.holiday_status_id.ex_public_holidays

            rest_days = []
            schedule_template = leave.employee_id \
                and leave.employee_id.contract_id \
                and leave.employee_id.contract_id.schedule_template_id
            if (ex_rd and schedule_template):
                rest_days = schedule_template \
                    .get_rest_days(schedule_template.id)

            if leave.number_of_days_temp:
                count_days = leave.number_of_days_temp
            else:
                count_days = (dt_to + timedelta(seconds=1) - dt_from).days
            no_days = 0
            real_days = 0
            ph_days = 0
            r_days = 0
            while count_days > 0:
                public_holiday = holiday_obj.is_public_holiday(next_dt.date(),
                    leave.employee_id.id)
                public_holiday = (public_holiday and ex_ph)
                rest_day = (next_dt.weekday() in rest_days and ex_rd)
                next_dt += timedelta(days=(1 if leave.number_of_days_temp
                                           else -1))

                if public_holiday or rest_day:
                    if public_holiday:
                        ph_days += 1
                    elif rest_day:
                        r_days += 1
                else:
                    if leave.number_of_days_temp:
                        count_days -= 1
                    no_days += 1
                real_days += 1
                if not leave.number_of_days_temp:
                    count_days -= 1

            if not leave.date_to:
                dt_to = next_dt - timedelta(seconds=1)
                leave.date_to = dt_to.astimezone(utc)
            elif not leave.date_from:
                leave.date_from = (next_dt + timedelta(seconds=1)) \
                    .astimezone(utc)

            leave.rest_days = r_days
            leave.public_holiday_days = ph_days
            leave.real_days = real_days
            leave.number_of_days_temp = no_days

            return_date = dt_to + timedelta(seconds=1)
            while ((return_date.weekday() in rest_days and ex_rd) or
                   (holiday_obj.is_public_holiday(return_date.date(),
                                                  leave.employee_id.id) and
                    ex_ph)):
                return_date += timedelta(days=1)
            leave.return_date = return_date.strftime('%B %d, %Y')

    @api.onchange('employee_id')
    def _onchange_employee(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
        self._compute_days()

    @api.onchange('holiday_status_id')
    def _onchange_holiday_status(self):
        self._compute_days()

    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from and not self._skip_compute_days:
            if self.number_of_days_temp:
                self.date_to = False
            self._compute_days()

    @api.onchange('date_to')
    def _onchange_date_to(self):
        if self.date_to and not self._skip_compute_days:
            if self.date_from:
                self.number_of_days_temp = False
            self._compute_days()

    @api.onchange('number_of_days_temp')
    def _onchange_number_of_days_temp(self):
        if self.number_of_days_temp and not self._skip_compute_days:
            if self.date_from:
                self.date_to = False
            self._compute_days()

    @api.model
    def create(self, vals):
        att_obj = self.env['hr.attendance']
        if (vals.get('date_from') and vals.get('date_to') and
                vals.get('type') == 'remove' and
                vals.get('holiday_type') == 'employee'):
            att_ids = att_obj.search(
                [
                    ('employee_id', '=', vals['employee_id']),
                    ('name', '>=', vals['date_from']),
                    ('name', '<=', vals['date_to'])
                ])
            if len(att_ids) > 0:
                raise exceptions.Warning(
                    _('Warning'),
                    _('There is already one or more attendance records for '
                      'the date you have chosen.')
                )
        return super(hr_holidays, self).create(vals)

    @api.multi
    def holidays_first_validate(self):
        self._check_validate()
        return super(hr_holidays, self).holidays_first_validate()

    @api.multi
    def holidays_validate(self):
        self._check_validate()
        return super(hr_holidays, self).holidays_validate()

    @api.multi
    def _check_validate(self):
        users_obj = self.env['res.users']
        if not users_obj.has_group('base.group_hr_manager'):
            for leave in self:
                if leave.employee_id.user_id.id == self.env.user.id:
                    raise exceptions.Warning(
                        _('Warning!'),
                        _('You cannot approve your own leave:\nHoliday Type: '
                          '%s\nEmployee: %s') % (leave.holiday_status_id.name,
                                                 leave.employee_id.name)
                    )
        return


class hr_attendance(models.Model):

    _name = 'hr.attendance'
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        if vals.get('name', False):
            lv_ids = self.env['hr.holidays'].search(
                [
                    ('employee_id', '=', vals['employee_id']),
                    ('type', '=', 'remove'),
                    ('date_from', '<=', vals['name']),
                    ('date_to', '>=', vals['name']),
                    ('state', 'not in', ['cancel', 'refuse'])
                ], context=context)
            if len(lv_ids) > 0:
                ee_data = self.env['hr.employee'].read(
                     vals['employee_id'], ['name']
                )
                raise orm.except_orm(
                    _('Warning'),
                    _("There is already one or more leaves recorded for the "
                      "date you have chosen:\n"
                      "Employee: %s\n"
                      "Date: %s" % (ee_data['name'], vals['name'])))

        return super(hr_attendance, self).create(vals)
