from odoo import _, api, fields, models
from odoo.http import request
from datetime import datetime
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _description = 'Stock Picking'
    
    dte_received_correctly = fields.Boolean(string='DTE Received Correctly', readonly=True, default=False)
    destination_partner_id = fields.Many2one('res.partner', string='Destination Partner')
    amount_total = fields.Float(string='Total Amount', default=0.0)
    
    def get_daily_token(self):
        company = self.env.user.company_id
        if not company.office_guide_expiry_date or company.office_guide_expiry_date < fields.Datetime.now():
            try:
                url = f'{company.office_guide_base_url}/api/login'
                params = {
                    'username': company.office_guide_username,
                    'password': company.office_guide_password
                }
                token_data = request.post(url, params)
            except Exception as e:
                raise ValidationError(_('Error al obtener el token diario: %s') % e)
            expiry_date = datetime.strptime(token_data.get('expira'), "%Y-%m-%d %H:%M:%S")
            token = token_data.get('token')
            company.write({
                'office_guide_expiry_date': expiry_date,
                'office_guide_token': token
            })
            return token
        return company.office_guide_token
    
    def get_register_single_dte(self):
        if not self.destination_partner_id:
            raise ValidationError(_('Debe ingresar un contacto del destino.'))
        company = self.env.user.company_id
        url = f'{company.office_guide_base_url}/api/register_single_dte'
        token = self.get_daily_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-type': 'application/json'
        }
        json_data = self.get_data_to_register_single_dte()
        data_register_single_dte = request.post(url, json_data, headers=headers)
        if data_register_single_dte.get('error'):
            raise ValidationError(_('Error al registrar el DTE: %s') % data_register_single_dte['error'].get('detalleRespuesta'))
        self.dte_received_correctly = True
        folio = json_data.get('Dte')[0].get('Folio')
        self.folio = folio
    
    def get_data_to_register_single_dte(self):
        folio = self.env['caf.folio'].get_next_folio()
        today = fields.Date.to_string(fields.Date.today())
        return  {
            "RUTEmisor": self.env.company.partner_id.vat,
            "TipoDTE": "52",
            "envioSII": "true",
            "Dte": [
                {
                    "RUTRecep": self.partner_id.docuemnt_number,
                    "GiroRecep":self.partner_id.activity_description,
                    "RznSocRecep": self.partner_id.name,
                    "DirRecep": self.partner_id.street,
                    "CmnaRecep":self.partner_id.city_id.name,
                    "CiudadRecep":self.partner_id.city,
                    "Contacto": self.partner_id.phone,
                    "Folio": folio,
                    "FchEmis": today,
                    "FchVenc": today,
                    "IndTraslado": "6", # ! a qué corresponde este campo?
                    "RUTTrans": self.destination_partner_id.docuemnt_number,
                    "DirDest":  self.destination_partner_id.street,
                    "CmnaDest":  self.destination_partner_id.city_id.name,
                    "CiudadDest":  self.destination_partner_id.city,
                    "MntTotal" : self.amount_total,
                    "Detalle": [
                        # ! ¿Qué es NmbItem, QtyItem, PrcItem, MontoItem, DscItem?
                        {
                            "NmbItem": "ONT",
                            "QtyItem": "50",
                            "PrcItem": 0,
                            "MontoItem": 0,
                            "DscItem": "modelo RWEWRW"
                        }
                    ]
                }
            ]
        }
        
    def get_binary_pdf_dte(self):
        if self.dte_received_correctly:
            company = self.env.user.company_id
            url = f'{company.office_guide_base_url}/api/facturacion/obtenerPDF'
            token = self.get_daily_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-type': 'application/json'
            }
            json_data = self.get_data_to_get_pdf_dte()
            data_binary_pdf_dte = request.post(url, json_data, headers=headers)
            if data_binary_pdf_dte.get('error'):
                raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_binary_pdf_dte['error'].get('detalleRespuesta'))
            binary_pdf = data_binary_pdf_dte['success'].get('detalleRespuesta')
        raise ValidationError(_('No se ha registrado el DTE correctamente'))
    
    def get_url_pdf_dte(self):
        if self.dte_received_correctly:
            company = self.env.user.company_id
            url = f'{company.office_guide_base_url}/api/facturacion/urlPDF'
            token = self.get_daily_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-type': 'application/json'
            }
            json_data = self.get_data_to_get_pdf_dte()
            data_url_pdf_dte = request.post(url, json_data, headers=headers)
            if data_url_pdf_dte.get('error'):
                raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_url_pdf_dte['error'].get('detalleRespuesta'))
            url_pdf = data_url_pdf_dte['success'].get('detalleRespuesta')
        raise ValidationError(_('No se ha registrado el DTE correctamente'))
    
    def get_data_to_get_pdf_dte(self):
        return {
            "rutEmisor": self.partner_id.vat,
            "folio": self.folio,
            "tipoDocumento": "52"
        }
        
    def _action_done(self):
        res = super(StockPicking, self)._action_done()
        self.get_register_single_dte()
        return res