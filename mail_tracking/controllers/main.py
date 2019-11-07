# Copyright 2016 Antonio Espinosa - <antonio.espinosa@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import werkzeug
import odoo
from contextlib import contextmanager
from odoo import api, http, SUPERUSER_ID

from odoo.addons.mail.controllers.main import MailController
import logging
import base64
_logger = logging.getLogger(__name__)

BLANK = 'R0lGODlhAQABAIAAANvf7wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=='


@contextmanager
def db_env(dbname):
    # This part you're missing and it's important
    if not http.db_filter([dbname]):
        raise werkzeug.exceptions.BadRequest()
    cr = None
    if dbname == http.request.db:
        cr = http.request.cr
    if not cr:
        cr = odoo.sql_db.db_connect(dbname).cursor()
    with api.Environment.manage():
        yield api.Environment(cr, SUPERUSER_ID, {})


class MailTrackingController(MailController):

    def _request_metadata(self):
        """Prepare remote info metadata"""
        request = http.request.httprequest
        return {
            'ip': request.remote_addr or False,
            'user_agent': request.user_agent or False,
            'os_family': request.user_agent.platform or False,
            'ua_family': request.user_agent.browser or False,
        }

    @http.route(['/mail/tracking/all/<string:db>',
                 '/mail/tracking/event/<string:db>/<string:event_type>'],
                type='http', auth='none', csrf=False)
    def mail_tracking_event(self, db, event_type=None, **kw):
        """Route used by external mail service"""
        metadata = self._request_metadata()
        res = None
        with db_env(db) as env:
            if env:
                res = env['mail.tracking.email'].event_process(
                    http.request, kw, metadata, event_type=event_type)
        return res or 'NOT FOUND'

    @http.route(['/mail/tracking/open/<string:db>'
                 '/<int:tracking_email_id>/blank.gif',
                 '/mail/tracking/open/<string:db>'
                 '/<int:tracking_email_id>/<string:token>/blank.gif'],
                type='http', auth='none')
    def mail_tracking_open(self, db, tracking_email_id, token=False, **kw):
        """Route used to track mail openned (With & Without Token)"""
        metadata = self._request_metadata()
        with db_env(db) as env:
            if env:
                tracking_email = env['mail.tracking.email'].search([
                    ('id', '=', tracking_email_id),
                    ('state', 'in', ['sent', 'delivered']),
                    ('token', '=', token),
                ])
                if tracking_email:
                    tracking_email.event_create('open', metadata)
                else:
                    _logger.warning(
                        "MailTracking email '%s' not found", tracking_email_id)

        # Always return GIF blank image
        response = werkzeug.wrappers.Response()
        response.mimetype = 'image/gif'
        response.data = base64.b64decode(BLANK)
        return response

    @http.route()
    def mail_init_messaging(self):
        """Route used to initial values of Discuss app"""
        values = super().mail_init_messaging()
        values.update({
            'failed_counter':
                http.request.env['mail.message'].get_failed_count(),
        })
        return values
