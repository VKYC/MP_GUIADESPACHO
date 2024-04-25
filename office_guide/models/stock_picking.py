from odoo import _, api, fields, models
from datetime import datetime
from odoo.exceptions import ValidationError
import requests
import logging


_logger = logging.getLogger(__name__)




class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _description = 'Stock Picking'
    
    dte_received_correctly = fields.Boolean(string='DTE Received Correctly', readonly=True, default=False)
    destination_partner_id = fields.Many2one('res.partner', string='Destination Partner')
    amount_total = fields.Float(string='Total Amount', default=0.0)
    url_pdf = fields.Char(string='URL PDF', readonly=True)
    binary_pdf = fields.Binary(string='Binary PDF', readonly=True)
    json_dte = fields.Char(string='JSON DTE', readonly=True)
    
    def get_daily_token(self):
        company = self.env.user.company_id
        if not company.office_guide_base_url or not company.office_guide_username or not company.office_guide_password:
            raise ValidationError(_('Debe configurar los datos de conexión de la guía de despacho.'))
        if not company.office_guide_expiry_date or company.office_guide_expiry_date < fields.Datetime.now():
            try:
                url = f'{company.office_guide_base_url}/api/login'
                params = {
                    'email': company.office_guide_username,
                    'password': company.office_guide_password
                }
                token_data = requests.post(url, data=params)
            except requests.exceptions.RequestException as e:
                raise ValidationError(_('Error de conexión: %s') % e)
            except requests.exceptions.HTTPError as e:
                raise ValidationError(_('Error HTTP: %s') % e)
            except Exception as e:
                raise ValidationError(_('Error al obtener el token diario: %s') % e)
            if token_data.status_code != 200:
                raise ValidationError(_('Error al obtener el token diario: %s') % token_data.text)
            token_data = token_data.json()
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
        url = f'{company.office_guide_base_url}/api/facturacion/registrarDTE'
        token = self.get_daily_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-type': 'application/json'
        }
        json_data = self.get_data_to_register_single_dte()
        data_register_single_dte = requests.post(url, data=json_data, headers=headers)
        # if data_register_single_dte.status_code != 200:
        #     raise ValidationError(_('Error al registrar el DTE: %s') % data_register_single_dte.text)
        data_register_single_dte = data_register_single_dte.json()
        if data_register_single_dte.get('error'):
            raise ValidationError(_('Error al registrar el DTE: %s') % data_register_single_dte['error'].get('detalleRespuesta'))
        self.dte_received_correctly = True
        folio = json_data.get('Dte')[0].get('Folio')
        self.folio = folio
    
    def get_data_to_register_single_dte(self):
        folio = self.env['caf.folio'].get_next_folio()
        today = fields.Date.to_string(fields.Date.today())
        detalle = []
        for det in self.move_ids_without_package:
            detalle.append({
                "NmbItem": det.product_id.name,
                "QtyItem": det.quantity_done,
                "PrcItem": det.product_id.product_tmpl_id.list_price,
                "MontoItem": det.product_id.product_tmpl_id.list_price * det.quantity_done,
                "DscItem": 0
            })
        
        json_dte = {
            "RUTEmisor": self.env.company.partner_id.vat,
            "TipoDTE": "52",
            "envioSII": True,
            "Dte": [
                {
                    "RUTRecep": self.partner_id.document_number,
                    "GiroRecep":self.partner_id.activity_description,
                    "RznSocRecep": self.partner_id.name,
                    "DirRecep": self.partner_id.street,
                    "CmnaRecep":self.partner_id.city_id.name,
                    "CiudadRecep":self.partner_id.city,
                    "Contacto": self.partner_id.phone,
                    "Folio": folio,
                    "FchEmis": today,
                    "FchVenc": today,
                    "IndTraslado": "5", # ! a qué corresponde este campo?
                    "RUTTrans": self.destination_partner_id.document_number,
                    "DirDest":  self.destination_partner_id.street,
                    "CmnaDest":  self.destination_partner_id.city_id.name,
                    "CiudadDest":  self.destination_partner_id.city,
                    "MntTotal" : self.amount_total,
                    "Detalle": detalle
                }
            ]
        }
        self.json_dte = json_dte
        _logger.info(f"datos del json {self.id} {json_dte}")
        return json_dte
        
        
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
            data_binary_pdf_dte = requests.post(url, data=json_data, headers=headers)
            # if data_binary_pdf_dte.status_code != 200:
            #     raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_binary_pdf_dte.text)
            data_binary_pdf_dte = data_binary_pdf_dte.json()
            if data_binary_pdf_dte.get('error'):
                raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_binary_pdf_dte['error'].get('detalleRespuesta'))
            binary_pdf = data_binary_pdf_dte['success'].get('detalleRespuesta')
            self.binary_pdf = binary_pdf
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
            data_url_pdf_dte = requests.post(url, data=json_data, headers=headers)
            # if data_url_pdf_dte.status_code != 200:
            #     raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_url_pdf_dte.text)
            data_url_pdf_dte = data_url_pdf_dte.json()
            if data_url_pdf_dte.get('error'):
                raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_url_pdf_dte['error'].get('detalleRespuesta'))
            url_pdf = data_url_pdf_dte['success'].get('detalleRespuesta')
            self.url_pdf - url_pdf
        raise ValidationError(_('No se ha registrado el DTE correctamente'))
    
    def get_data_to_get_pdf_dte(self):
        return {
            "rutEmisor": self.partner_id.vat,
            "folio": self.folio,
            "tipoDocumento": "52"
        }
        
    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        if self:
            self.get_register_single_dte()
        return res