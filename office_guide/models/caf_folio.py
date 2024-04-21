from odoo import _, api, fields, models
import xml.etree.ElementTree as ET
import base64
from odoo.exceptions import ValidationError
import logging


_logger = logging.getLogger(__name__)



class CafFolio(models.Model):
    _name = 'caf.folio'
    _description = 'Caf Folio'
    
    caf_xml = fields.Binary(string='Archivo XML')
    name_caf_folio = fields.Char(string='Nombre CAF')
    init_date = fields.Date(string='Fecha Inicio')
    end_date = fields.Date(string='Fecha Fin')
    init_folio = fields.Integer(string='Folio Inicial')
    end_folio = fields.Integer(string='Folio Final')
    active = fields.Boolean(string='Activo', default=False)
    next_folio = fields.Integer(string='Siguiente Folio', compute='_compute_next_folio', store=True)
    
    @api.constrains('active')
    def _check_campo_booleano_uno(self):
        # Obtener todos los registros con active=True
        true_records = self.env['caf.folio'].search([('active', '=', True)])

        # Si hay más de un registro con active=True, lanzar una excepción de validación
        if len(true_records) > 1:
            raise ValidationError("Solo puede haber un registro con active True.")

    @api.onchange('caf_xml')
    def read_xml(self):
        for record in self:
            if record.caf_xml:
                # Obtener el contenido del campo binario
                contenido = base64.b64decode(record.caf_xml)

                # Parsear el contenido como XML
                tree = ET.fromstring(contenido)

                # Acceder a los elementos y atributos del árbol XML
                record.init_folio = tree.find("CAF").find('DA').find('RNG').find('D').text
                record.end_folio = tree.find("CAF").find('DA').find('RNG').find('H').text
                end_date = tree.find("CAF").find('DA').find('FA').text
                record.end_date = fields.Date.from_string(end_date)