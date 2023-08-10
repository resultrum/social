# Copyright 2021 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import UserError


class MailTemplate(models.Model):
    _inherit = "mail.template"

    template_report_ids = fields.One2many(
        comodel_name="mail.template.report", inverse_name="mail_template_id",
    )

    # pylint: disable=redefined-outer-name
    def generate_email(self, res_ids, fields=None):
        """
        Inherit to generate attachments.
        Inspired from :
         - original mail.template,generate_email(...) from Odoo.
         - mail template multi attachment from Acsone OCA addon
        """
        self.ensure_one()
        multi_mode = True
        results = super(MailTemplate, self).generate_email(
            res_ids,
            fields=fields
        )
        if not self.template_report_ids:
            return results
        if isinstance(res_ids, int):
            multi_mode = False
            results = {res_ids: results}
        for res_id, values in results.items():
            attachments = values.setdefault("attachments", [])
            for template_report in self.template_report_ids:
                if not self.check_condition(
                    values['model'],
                    res_id,
                    template_report.sudo().field_name_condition
                ):
                    continue
                report_name = self._render_template(
                    template_report.report_name, template_report.model, res_id
                )
                report = template_report.report_template_id
                report_service = report.report_name

                if report.report_type in ["qweb-html", "qweb-pdf"]:
                    result, report_format = report.render_qweb_pdf([res_id])
                else:
                    res = report.render([res_id])
                    if not res:
                        raise exceptions.UserError(
                            _("Unsupported report type %s found."
                              ) % report.report_type
                        )
                    result, report_format = res
                result = base64.b64encode(result)
                if not report_name:
                    report_name = "report." + report_service
                ext = "." + report_format
                if not report_name.endswith(ext):
                    report_name += ext
                attachments.append((report_name, result))
        return results if multi_mode else results[res_ids]

    @api.model
    def check_condition(self, model, res_id, field_name_condition):
        record = self.env[model].browse(res_id)
        if not field_name_condition:
            return True
        if field_name_condition not in record._fields:
            raise UserError(_(
                'Unknown field (%s) on model (%s)'
            ) % (field_name_condition, model))
        return record[field_name_condition]
