# -*- coding: utf-8 -*-
# © 2016 Xpansa Group <https://www.xpansa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import models, fields, api


class HumanResourcesConfiguration(models.TransientModel):
    _inherit = 'hr.config.settings'

    birthday_reminder_before = fields.Integer('Birthday Reminder Before')

    @api.multi
    def set_birthday_reminder_before(self):
        icp = self.env['ir.config_parameter']
        icp.set_param('birthday_reminder.before', self.birthday_reminder_before)

    @api.model
    def get_default_birthday_reminder_before(self, fields):
        icp = self.env['ir.config_parameter']
        return {
            'birthday_reminder_before': int(icp.get_param('birthday_reminder.before', '0'))
        }
