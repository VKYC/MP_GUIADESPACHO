from odoo import _, api, fields, models
from datetime import datetime
from odoo.exceptions import ValidationError
import requests
import json
import base64
import logging


_logger = logging.getLogger(__name__)




class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _description = 'Stock Picking'
    
    dte_received_correctly = fields.Boolean(string='DTE Received Correctly', readonly=True, default=False, copy=False)
    destination_partner_id = fields.Many2one('res.partner', string='Destination Partner')
    amount_total = fields.Float(string='Total Amount', default=0.0)
    url_pdf = fields.Char(string='URL PDF', readonly=True, copy=False)
    binary_pdf = fields.Binary(string='Binary PDF', readonly=True, copy=False)
    json_dte = fields.Text(string='JSON DTE', readonly=True, copy=False)
    folio = fields.Integer(string='Folio', readonly=True, copy=False)
    
    def get_token(self, company):
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
    
    def get_daily_token(self):
        company = self.env.user.company_id
        if self.env.context.get('force_token'):
            return self.get_token(company)
        if not company.office_guide_base_url or not company.office_guide_username or not company.office_guide_password:
            raise ValidationError(_('Debe configurar los datos de conexión de la guía de despacho.'))
        if not company.office_guide_token or company.office_guide_expiry_date < fields.Datetime.now():
            self.get_token(company)
        return company.office_guide_token
    
    def get_register_single_dte(self):
        if self.dte_received_correctly:
            raise ValidationError(_('Guía de despacho ya registrada.'))
        if not self.destination_partner_id:
            raise ValidationError(_('Debe ingresar un contacto del destino.'))
        company = self.env.user.company_id
        url = f'{company.office_guide_base_url}/api/facturacion/registrarDTE'
        token = self.get_daily_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-type': 'application/json'
        }
        json_dte = self.get_data_to_register_single_dte()
        data_register_single_dte = requests.post(url, json=json_dte, headers=headers)
        data_register_single_dte = data_register_single_dte.json()
        if data_register_single_dte.get('error'):
            if data_register_single_dte.get('codigo') == 401:
                self.with_context(force_token=True).get_register_single_dte()
            else:
                raise ValidationError(_('Error al registrar el DTE: %s\n%s') % (data_register_single_dte['error'].get('detalleRespuesta'), json_dte))
        self.dte_received_correctly = True
        folio = json_dte.get('Dte')[0].get('Folio')
        self.folio = folio
    
    def get_data_to_register_single_dte(self):
        folio = self.env['caf.folio'].get_next_folio()
        today = fields.Date.to_string(fields.Date.today())
        detalle = []
        for det in self.move_line_nosuggest_ids:
            if not det.product_id.name:
                raise ValidationError(_('Debe ingresar un nombre del producto.'))
            if not det.qty_done:
                raise ValidationError(_('Debe ingresar una cantidad del producto.'))
            detalle.append({
                "NmbItem": 'Traslado - No Constituye Venta :',
                "QtyItem": det.qty_done,
                "PrcItem": 0,
                "MontoItem": 0,
                "DscItem": det.product_id.name
            })
        if not self.env.company.partner_id.vat:
            raise ValidationError(_('Debe ingresar un RUT del emisor.'))
        if not self.partner_id.document_number:
            raise ValidationError(_('Debe ingresar un RUT del receptor.'))
        if not self.partner_id.activity_description.name:
            raise ValidationError(_('Debe ingresar un giro del receptor.'))
        if not self.partner_id.name:
            raise ValidationError(_('Debe ingresar una razón social del receptor.'))
        if not self.partner_id.street:
            raise ValidationError(_('Debe ingresar una dirección del receptor.'))
        if not self.partner_id.city_id.name:
            raise ValidationError(_('Debe ingresar una comuna del receptor.'))
        if not self.partner_id.city:
            raise ValidationError(_('Debe ingresar una ciudad del receptor.'))
        if not self.partner_id.phone:
            raise ValidationError(_('Debe ingresar un contacto del receptor.'))
        if not self.destination_partner_id.document_number:
            raise ValidationError(_('Debe ingresar un RUT del transportista.'))
        if not self.destination_partner_id.street:
            raise ValidationError(_('Debe ingresar una dirección del transportista.'))
        if not self.destination_partner_id.city_id.name:
            raise ValidationError(_('Debe ingresar una comuna del transportista.'))
        if not self.destination_partner_id.city:
            raise ValidationError(_('Debe ingresar una ciudad del transportista.'))
        json_dte = {
            "RUTEmisor": self.env.company.partner_id.vat.replace('.', ''),
            "TipoDTE": "52",
            "envioSII": True,
            "Dte": [
                {
                    "RUTRecep": self.partner_id.document_number.replace('.', ''),
                    "GiroRecep":self.partner_id.activity_description.name,
                    "RznSocRecep": self.partner_id.name,
                    "DirRecep": self.partner_id.street,
                    "CmnaRecep":self.partner_id.city_id.name,
                    "CiudadRecep":self.partner_id.city,
                    "Contacto": self.partner_id.phone,
                    "Folio": folio,
                    "FchEmis": today,
                    "FchVenc": today,
                    "IndTraslado": "5",
                    "RUTTrans": self.destination_partner_id.document_number,
                    "DirDest":  self.destination_partner_id.street,
                    "CmnaDest":  self.destination_partner_id.city_id.name,
                    "CiudadDest":  self.destination_partner_id.city,
                    "MntTotal" : 0,
                    "Detalle": detalle,
                }
            ]
        }
        self.json_dte = json.dumps(json_dte)
        _logger.info(f"datos del json {self.id} {json_dte}")
        return json_dte
        
        
    def get_binary_pdf_dte(self):
        if self.dte_received_correctly:
            company = self.env.user.company_id
            url = f'{company.office_guide_base_url}/api/facturacion/obtenerPDF'
            token = self.get_daily_token()
            headers = {
                'Authorization': f'Bearer {token}',
                # 'Content-type': 'application/json'
            }
            json_data = self.get_data_to_get_pdf_dte()
            data_binary_pdf_dte = requests.post(url, data=json_data, headers=headers)
            data_binary_pdf_dte = data_binary_pdf_dte.json()
            if data_binary_pdf_dte.get('error'):
                if data_binary_pdf_dte.get('codigo') == 401:
                    self.with_context(force_token=True).get_binary_pdf_dte()
                else:
                    raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_binary_pdf_dte['error'].get('detalleRespuesta'))
            binary_pdf = data_binary_pdf_dte['success'].get('descripcionRespuesta').get('documentoPdf')
            self.binary_pdf = base64.b64decode(binary_pdf)
        raise ValidationError(_('No se ha registrado el DTE correctamente'))
    
    def get_url_pdf_dte(self):
        if self.dte_received_correctly:
            company = self.env.user.company_id
            url = f'{company.office_guide_base_url}/api/facturacion/urlPDF'
            token = self.get_daily_token()
            headers = {
                'Authorization': f'Bearer {token}',
                # 'Content-type': 'application/json'
            }
            json_data = self.get_data_to_get_pdf_dte()
            data_url_pdf_dte = requests.post(url, data=json_data, headers=headers)
            data_url_pdf_dte = data_url_pdf_dte.json()
            if data_url_pdf_dte.get('error'):
                if data_url_pdf_dte.get('codigo') == 401:
                    self.with_context(force_token=True).get_url_pdf_dte()
                else:
                    raise ValidationError(_('Error al obtener el PDF del DTE: %s') % data_url_pdf_dte['error'].get('detalleRespuesta'))
            url_pdf = data_url_pdf_dte['success'].get('descripcionRespuesta').get('urlPdf')
            self.url_pdf = url_pdf
        raise ValidationError(_('No se ha registrado el DTE correctamente'))
    
    def get_data_to_get_pdf_dte(self):
        return {
            "rutEmisor": self.partner_id.vat,
            "folio": self.folio,
            "tipoDocumento": "52"
        }