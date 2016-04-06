# -*- coding: utf-8 -*-
# © 2016 Xpansa Group <https://www.xpansa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import datetime, timedelta
from openerp import models, fields, api


class HrEmployee(models.Model):

    _inherit = 'hr.employee'

    @api.model
    def birthday_reminder_cron(self):
        icp = self.env['ir.config_parameter']
        imd = self.env['ir.model.data']
        et = self.env['email.template']
        rl = self.env['res.lang']
        now = datetime.now() + \
            timedelta(days=int(icp.get_param('birthday_reminder.before', '0')))
        template = imd.get_object('hr_birthday_reminder',
                                  'hr_birthday_reminder_template')
        employees = self.search([]) 
        for emp in employees:
            if not emp.birthday:
                continue
            bdt = fields.Date.from_string(emp.birthday).replace(year=now.year)
            if bdt.day == now.day and bdt.month == now.month:
                for receiver in employees:
                    lang = receiver.user_id and receiver.user_id.lang \
                        or receiver.company_id.partner_id.lang
                    date_format = rl.search([('code', '=', lang)]).date_format or '%d/%m/%Y'
                    template.with_context({
                        'employee': emp,
                        'birthday': bdt.strftime(date_format)
                    }).send_mail(receiver.id, force_send=True)
