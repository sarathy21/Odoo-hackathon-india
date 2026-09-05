# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home as WebHome

class DealFlowHome(WebHome):
    """
    Override /web/login to eliminate the 400 Bad Request 'Session expired (invalid CSRF token)'
    error when switching users or when browser tabs submit with stale/rotated session tokens.
    Authentication is still strictly and securely verified against user credentials via
    request.session.authenticate().
    """

    @http.route('/web/login', type='http', auth="none", csrf=False, readonly=False)
    def web_login(self, *args, **kw):
        return super().web_login(*args, **kw)
