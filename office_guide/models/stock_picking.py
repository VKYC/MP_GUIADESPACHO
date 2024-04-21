from odoo import _, api, fields, models
from odoo.http import request
from datetime import datetime
from odoo.exceptions import ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _description = 'Stock Picking'
    
    dte_received_correctly = fields.Boolean(string='DTE Received Correctly', readonly=True, default=False)
    
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
    
    def get_data_to_register_single_dte(self):
        return  {
            "RUTEmisor": "77494541-5",
            "TipoDTE": "52",
            "envioSII": "true",
            "Dte": [
                {
                    "RUTRecep": "96722400-6",
                    "GiroRecep": "OTRAS ACTIVIDADES",
                    "RznSocRecep": "PACIFICO CALBE SPA",
                    "DirRecep": "AVENIDA TRES PONIENTE 235",
                    "CmnaRecep": "SAN PEDRO DE LA PAZ",
                    "CiudadRecep": "SAN PEDRO DE LA PAZ",
                    "Contacto": "959160531",
                    "Folio": 18,
                    "FchEmis": "2024-04-11",
                    "FchVenc": "2024-04-11",
                    "IndTraslado": "6",
                    "RUTTrans": "12.345.678-5",
                    "DirDest": "AVENIDA MAIPU  3243",
                    "CmnaDest": "CONCEPCION",
                    "CiudadDest": "CONCEPCION",
                    "MntTotal" : 0,
                    "Detalle": [
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
            "rutEmisor": "77494541-5",
            "folio": 18,
            "tipoDocumento": "52"
        }
        
    def _action_done(self):
        res = super(StockPicking, self)._action_done()
        self.get_register_single_dte()
        return res