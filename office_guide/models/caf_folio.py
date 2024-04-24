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
    init_folio = fields.Integer(string='Folio Inicial')
    end_folio = fields.Integer(string='Folio Final')
    active = fields.Boolean(string='Activo', default=False)
    next_folio = fields.Integer(string='Siguiente Folio')
    equal_end_next_folio = fields.Boolean(string='Igual a Folio Final', default=False, compute='_compute_equal_end_next_folio')
    
    _sql_constraints = [
        ("init_folio_unique", "unique(init_folio)", "El folio inicial debe ser único."),
    ]

    @api.constrains('active')
    def _check_campo_booleano_uno(self):
        # Obtener todos los registros con active=True
        true_records = self.env['caf.folio'].search([('active', '=', True)])

        # Si hay más de un registro con active=True, lanzar una excepción de validación
        if len(true_records) > 1:
            raise ValidationError("Solo puede haber un registro con active True.")
        
    @api.model
    def create(self, vals):
        res = super(CafFolio, self).create(vals)
        res.read_xml()
        return res

    # @api.onchange('caf_xml')
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
                init_date = tree.find("CAF").find('DA').find('FA').text
                record.init_date = fields.Date.from_string(init_date)
                
    @api.depends('end_folio', 'next_folio')
    def _compute_equal_end_next_folio(self):
        for record in self:
            record.equal_end_next_folio = record.end_folio == record.next_folio
                
    @api.model
    def get_next_folio(self):
        # Obtener el registro activo
        date_today = fields.Date.today()
        active_record = self.env['caf.folio'].search([('active', '=', True), ('init_date', '>=', date_today)])
        records = self.env['caf.folio'].search([('equal_end_next_folio', '=', False), ('init_date', '>=', date_today)], order='init_folio asc')
        if not active_record:
            if not records:
                raise ValidationError("No hay un CAF.")
            active_record = records[0]
            active_record.active = True
        if not active_record.next_folio:
            active_record.next_folio = active_record.init_folio
        next_folio = active_record.next_folio
        if active_record.next_folio == active_record.end_folio:
            active_record.active = False
            new_active_record = self.env['caf.folio'].search([('active', '=', False), ('equal_end_next_folio', '=', False), ('init_folio', '>', active_record.next_folio), ('init_date', '>=', date_today)], limit=1, order='init_folio asc')
            new_active_record.active = True
        else:
            active_record.next_folio += 1
        return next_folio