# -*- coding: utf-8 -*-
# © 2016 Xpansa Group <https://www.xpansa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    'name': 'HR Birthday Reminder',
    'version': '1.0',
    'category': 'Generic Modules/Human Resources',
    'author': "Xpansa Group,"
              "Odoo Community Association (OCA)",
    'website': 'https://www.xpansa.com',
    'license': 'AGPL-3',
    'depends': [
        'hr',
    ],
    'data': [
        'views/hr_birthday_reminder_views.xml',
        'views/hr_birthday_reminder_config.xml',
        'views/hr_birthday_reminder_cron.xml',
    ],
    'installable': True,
}
