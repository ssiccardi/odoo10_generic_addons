# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo import tools, SUPERUSER_ID
import odoo.http as http
from odoo.http import request
from odoo.addons.web.controllers.main import ExcelExport
from datetime import datetime, date
from odoo.tools.float_utils import float_round, float_compare
import math
from cStringIO import StringIO
import pytz

try:
    import json
except ImportError:
    import simplejson as json
    
try:
    import xlwt
except ImportError:
    xlwt = None

## HOWTO fix the Unicode special characters issue
## https://stackoverflow.com/questions/21129020/how-to-fix-unicodedecodeerror-ascii-codec-cant-decode-byte
import sys
reload(sys)
sys.setdefaultencoding('utf8')

db_monodb = http.db_monodb

class ExcelExportView(ExcelExport):

    @http.route('/cq_stock_10/exportmargini', type='http', auth='user')
    def esporta_margini(self, data, token):
        data = json.loads(data)
        lotgruped = data.get('lotgruped', False)
        context = data.get('context', {})
        uid = context.get('uid', SUPERUSER_ID)
        domain = data.get('domain',[])

        dbname = False
        if request.session.db:
            dbname = request.session.db
        elif dbname is None:
            dbname = db_monodb()

        if not dbname:
            return

        with odoo.api.Environment.manage():
            with odoo.registry(dbname).cursor() as new_cr:
                env = odoo.api.Environment(new_cr, uid, context)
                if lotgruped and not env.user.has_group('stock.group_production_lot'):
                    return
                round_cur = env.user.company_id and env.user.company_id.currency_id.decimal_places or 2
                workbook = xlwt.Workbook(encoding='utf8')
                worksheet = workbook.add_sheet('Margini Prodotti')
                base_style = xlwt.easyxf('align: wrap yes')
                currency_style = xlwt.easyxf(num_format_str=u"[$€-410]#,##0." + "0"*round_cur)
                head_style = xlwt.easyxf('font: bold on;align: wrap yes;pattern: pattern solid, fore_color 27;')
                
                if not lotgruped:
                    worksheet.write(0, 0, 'Prodotto', head_style)
                    worksheet.col(0).width = 20000
                    worksheet.write(0, 1, 'Quantità', head_style)
                    worksheet.col(1).width = 4000
                    worksheet.write(0, 2, 'Unità di Misura', head_style)
                    worksheet.col(2).width = 5000
                    worksheet.write(0, 3, 'Ricavo', head_style)
                    worksheet.col(3).width = 5000
                    worksheet.write(0, 4, 'Costo', head_style)
                    worksheet.col(4).width = 5000
                    worksheet.write(0, 5, 'Margine', head_style)
                    worksheet.col(5).width = 5000
                    worksheet.write(0, 6, 'Margine Unitario', head_style)
                    worksheet.col(6).width = 5000
                    i = 0
                    for line in env['stock.quant'].read_group(domain, ['product_id','qty','price_out','price_in','margine','margine_u'], ['product_id']):
                        uom = env['product.product'].browse(line['product_id'][0]).uom_id
                        if uom:
                            uom_name = uom.name
                            round_uom = uom.decimal_places
                        else:
                            uom_name = ''
                            round_uom = 2
                        if float_compare(line['qty'], 0, round_uom) > 0:
                            i += 1
                            uom_format = xlwt.easyxf(num_format_str='#,##0' + (round_uom and '.'+'0'*round_uom or ''))
                            worksheet.write(i, 0, line['product_id'][1], base_style)
                            worksheet.write(i, 1, float_round(line['qty'], round_uom), uom_format)
                            worksheet.write(i, 2, uom_name, base_style)
                            worksheet.write(i, 3, float_round(line['price_out'], round_cur), currency_style)
                            worksheet.write(i, 4, float_round(line['price_in'], round_cur), currency_style)
                            worksheet.write(i, 5, float_round(line['margine'], round_cur), currency_style)
                            worksheet.write(i, 6, float_round(line['margine_u'], round_cur), currency_style)
                else:
                    worksheet.write(0, 0, 'Prodotto', head_style)
                    worksheet.col(0).width = 20000
                    worksheet.write(0, 1, 'Lotto', head_style)
                    worksheet.col(1).width = 10000
                    worksheet.write(0, 2, 'Quantità', head_style)
                    worksheet.col(2).width = 4000
                    worksheet.write(0, 3, 'Unità di Misura', head_style)
                    worksheet.col(3).width = 5000
                    worksheet.write(0, 4, 'Ricavo', head_style)
                    worksheet.col(4).width = 5000
                    worksheet.write(0, 5, 'Costo', head_style)
                    worksheet.col(5).width = 5000
                    worksheet.write(0, 6, 'Margine', head_style)
                    worksheet.col(6).width = 5000
                    worksheet.write(0, 7, 'Margine Unitario', head_style)
                    worksheet.col(7).width = 5000
                    i = 0
                    for line in env['stock.quant'].read_group(domain, ['product_id','qty','price_out','price_in','margine','margine_u'], ['product_id']):
                        uom = env['product.product'].browse(line['product_id'][0]).uom_id
                        if uom:
                            uom_name = uom.name
                            round_uom = uom.decimal_places
                        else:
                            uom_name = ''
                            round_uom = 2
                        if float_compare(line['qty'], 0, round_uom) > 0:
                            i += 1
                            uom_format = xlwt.easyxf(num_format_str='#,##0' + (round_uom and '.'+'0'*round_uom or ''))
                            worksheet.write(i, 0, line['product_id'][1], base_style)
                            worksheet.write(i, 2, float_round(line['qty'], round_uom), uom_format)
                            worksheet.write(i, 3, uom_name, base_style)
                            worksheet.write(i, 4, float_round(line['price_out'], round_cur), currency_style)
                            worksheet.write(i, 5, float_round(line['price_in'], round_cur), currency_style)
                            worksheet.write(i, 6, float_round(line['margine'], round_cur), currency_style)
                            worksheet.write(i, 7, float_round(line['margine_u'], round_cur), currency_style)
                            nwdomain = domain + [['product_id','=',line['product_id'][0]]]
                            for lot in env['stock.quant'].read_group(nwdomain, ['lot_id','qty','price_out','price_in','margine','margine_u'], ['lot_id']):
                                if float_compare(lot['qty'], 0, round_uom) > 0:
                                    i += 1
                                    worksheet.write(i, 1, lot['lot_id'] and lot['lot_id'][1] or 'Non definito', base_style)
                                    worksheet.write(i, 2, float_round(lot['qty'], round_uom), uom_format)
                                    worksheet.write(i, 3, uom_name, base_style)
                                    worksheet.write(i, 4, float_round(lot['price_out'], round_cur), currency_style)
                                    worksheet.write(i, 5, float_round(lot['price_in'], round_cur), currency_style)
                                    worksheet.write(i, 6, float_round(lot['margine'], round_cur), currency_style)
                                    worksheet.write(i, 7, float_round(lot['margine_u'], round_cur), currency_style)
                fp = StringIO()
                workbook.save(fp)
                fp.seek(0)
                file_data = fp.read()
                fp.close()
                tz = context.get('tz',False) and pytz.timezone(context['tz']) or pytz.utc
                return request.make_response(
                    file_data,
                    headers=[
                        ('Content-Disposition', 'attachment; filename="%s"'
                         % self.filename("margini_prodotti_%s"%datetime.strftime(datetime.now(tz=tz),'%d-%m-%Y'))),
                        ('Content-Type', self.content_type)            
                    ],
                    cookies={'fileToken': token}
                )

    @http.route('/cq_stock_10/exportstockhistory', type='http', auth='user')
    def esporta_stockhistory(self, data, token):
        data = json.loads(data)
        lotgruped = data.get('lotgruped', False)
        context = data.get('context', {})
        uid = context.get('uid', SUPERUSER_ID)
        domain = data.get('domain',[])
        inv_date = context.get('history_date', '')

        dbname = False
        if request.session.db:
            dbname = request.session.db
        elif dbname is None:
            dbname = db_monodb()

        if not dbname:
            return

        with odoo.api.Environment.manage():
            with odoo.registry(dbname).cursor() as new_cr:
                env = odoo.api.Environment(new_cr, uid, context)
                round_cur = env.user.company_id and env.user.company_id.currency_id.decimal_places or 2
                if lotgruped and not env.user.has_group('stock.group_production_lot'):
                    return
                workbook = xlwt.Workbook(encoding='utf8')
                base_style = xlwt.easyxf('align: wrap yes')
                head_style = xlwt.easyxf('font: bold on;align: wrap yes;pattern: pattern solid, fore_color 27;')
                currency_style = xlwt.easyxf(num_format_str=u"[$€-410]#,##0." + "0"*round_cur)
                total_style = xlwt.easyxf('font: bold on;align: wrap yes;')
                currency_style_total = xlwt.easyxf('font: bold on;align: wrap yes;', num_format_str=u"[$€-410]#,##0." + "0"*round_cur)

                if not lotgruped:
                    for location_group in env['stock.history'].read_group(domain, ['location_id','inventory_value'], ['location_id']):
                        worksheet = workbook.add_sheet(location_group['location_id'][1].replace('/','-'))
                        worksheet.write(0, 0, 'Prodotto', head_style)
                        worksheet.col(0).width = 20000
                        worksheet.write(0, 1, 'Quantità', head_style)
                        worksheet.col(1).width = 4000
                        worksheet.write(0, 2, 'Unità di Misura', head_style)
                        worksheet.col(2).width = 5000
                        worksheet.write(0, 3, 'Valore', head_style)
                        worksheet.col(3).width = 5000
                        tdomain = domain + [['location_id','=',location_group['location_id'][0]]]
                        i = 0
                        for line in env['stock.history'].read_group(tdomain,['product_id','quantity','inventory_value'], ['product_id']):
                            uom = env['product.product'].browse(line['product_id'][0]).uom_id
                            if uom:
                                uom_name = uom.name
                                round_uom = uom.decimal_places
                            else:
                                uom_name = ''
                                round_uom = 2
                            if float_compare(line['quantity'], 0, round_uom) > 0:
                                i += 1
                                uom_format = xlwt.easyxf(num_format_str='#,##0' + (round_uom and '.'+'0'*round_uom or ''))
                                worksheet.write(i, 0, line['product_id'][1], base_style)
                                worksheet.write(i, 1, float_round(line['quantity'], round_uom), uom_format)
                                worksheet.write(i, 2, uom_name, base_style)
                                worksheet.write(i, 3, float_round(line['inventory_value'], round_cur), currency_style)
                        i += 2
                        worksheet.write(i, 2, 'Totale', total_style)
                        worksheet.write(i, 3, float_round(location_group['inventory_value'], round_cur), currency_style_total)
                else:
                    for location_group in env['stock.history'].read_group(domain, ['location_id','inventory_value'], ['location_id']):
                        worksheet = workbook.add_sheet(location_group['location_id'][1].replace('/','-'))
                        worksheet.write(0, 0, 'Prodotto', head_style)
                        worksheet.col(0).width = 20000
                        worksheet.write(0, 1, 'Lotto', head_style)
                        worksheet.col(1).width = 10000
                        worksheet.write(0, 2, 'Quantità', head_style)
                        worksheet.col(2).width = 4000
                        worksheet.write(0, 3, 'Unità di Misura', head_style)
                        worksheet.col(3).width = 5000
                        worksheet.write(0, 4, 'Valore', head_style)
                        worksheet.col(4).width = 5000
                        tdomain = domain + [['location_id','=',location_group['location_id'][0]]]
                        i = 0
                        for line in env['stock.history'].read_group(tdomain, ['product_id','quantity','inventory_value'], ['product_id']):
                            uom = env['product.product'].browse(line['product_id'][0]).uom_id
                            if uom:
                                uom_name = uom.name
                                round_uom = uom.decimal_places
                            else:
                                uom_name = ''
                                round_uom = 2
                            if float_compare(line['quantity'], 0, round_uom) > 0:
                                i += 1
                                uom_format = xlwt.easyxf(num_format_str='#,##0' + (round_uom and '.'+'0'*round_uom or ''))
                                worksheet.write(i, 0, line['product_id'][1], base_style)
                                worksheet.write(i, 2, float_round(line['quantity'], round_uom), uom_format)
                                worksheet.write(i, 3, uom_name, base_style)
                                worksheet.write(i, 4, float_round(line['inventory_value'], round_cur), currency_style)
                                ttdomain = tdomain + [['product_id','=',line['product_id'][0]]]
                                for lot in env['stock.history'].read_group(ttdomain, ['serial_number','quantity','inventory_value'], ['serial_number']):
                                    if float_compare(lot['quantity'], 0, round_uom) > 0:
                                        i += 1
                                        worksheet.write(i, 1, lot['serial_number'] or 'Non definito', base_style)
                                        worksheet.write(i, 2, float_round(lot['quantity'], round_uom), uom_format)
                                        worksheet.write(i, 3, uom_name, base_style)
                                        worksheet.write(i, 4, float_round(lot['inventory_value'], round_cur), currency_style)
                        i += 2
                        worksheet.write(i, 3, 'Totale', total_style)
                        worksheet.write(i, 4, float_round(location_group['inventory_value'], round_cur), currency_style_total)
                fp = StringIO()
                workbook.save(fp)
                fp.seek(0)
                file_data = fp.read()
                fp.close()
                if inv_date:
                    tz = context.get('tz',False) and pytz.timezone(context['tz']) or pytz.utc
                    inv_date = pytz.utc.localize(datetime.strptime(inv_date, tools.DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(tz=tz)
                    inv_date = datetime.strftime(inv_date, '%d-%m-%Y_%H-%M-%S')
                return request.make_response(
                    file_data,
                    headers=[
                        ('Content-Disposition', 'attachment; filename="%s"'
                         % self.filename("inventario_%s"%inv_date)),
                        ('Content-Type', self.content_type)            
                    ],
                    cookies={'fileToken': token}
                )
