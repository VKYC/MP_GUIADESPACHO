from odoo import _, api, fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'
    _description = 'Res Company'
    
    office_guide_base_url = fields.Char(string='Office Guide Base URL')
    office_guide_username = fields.Char(string='Office Guide Username')
    office_guide_password = fields.Char(string='Office Guide Password', password=True)
    office_guide_expiry_date = fields.Datetime(string='Office Guide Expiry Date')
    office_guide_token = fields.Char(string='Office Guide Token')