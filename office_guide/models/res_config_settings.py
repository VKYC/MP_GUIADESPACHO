from odoo import _, api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _description = 'Res Config Settings'
    
    office_guide_base_url = fields.Char(string='Office Guide Base URL', related='company_id.office_guide_base_url', readonly=False)
    office_guide_username = fields.Char(string='Office Guide Username', related='company_id.office_guide_username', readonly=False)
    office_guide_password = fields.Char(string='Office Guide Password', related='company_id.office_guide_password', readonly=False, password=True)
    office_guide_expiry_date = fields.Datetime(string='Office Guide Expiry Date', related='company_id.office_guide_expiry_date', readonly=False)
    office_guide_token = fields.Char(string='Office Guide Token', related='company_id.office_guide_token', readonly=False)