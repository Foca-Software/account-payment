# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    open_move_line_ids = fields.One2many("account.move.line", compute="_compute_open_move_lines")
    pay_now_journal_id = fields.Many2one(
        "account.journal",
        "Pay now Journal",
        help="If you set a journal here, after invoice validation, the invoice"
        " will be automatically paid with this journal. As manual payment"
        "method is used, only journals with manual method are shown.",
        # use copy false for two reasons:
        # 1. when making refund it's safer to make pay now empty (specially if automatic refund validation is enable)
        # 2. on duplicating an invoice it's safer also
        copy=False,
    )

    @api.depends("line_ids.account_id.account_type", "line_ids.reconciled")
    def _compute_open_move_lines(self):
        for rec in self:
            rec.open_move_line_ids = rec.line_ids.filtered(
                lambda r: not r.reconciled
                and r.parent_state == "posted"
                and r.account_id.account_type in self.env["account.payment"]._get_valid_payment_account_types()
            )

    def pay_now(self):
        for rec in self.filtered(lambda x: x.pay_now_journal_id and x.state == 'posted'
                                            and x.payment_state in ('not_paid', 'partial')):

            receivable_lines = rec.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and not l.reconciled
            )

            if not receivable_lines:
                continue

            wizard = self.env['account.payment.register'].with_context(
                active_model='account.move.line',
                active_ids=receivable_lines.ids
            ).create({
                'journal_id': rec.pay_now_journal_id.id,
                'payment_date': rec.invoice_date,
                'amount': abs(rec.amount_residual),
            })

            payments = wizard._create_payments()

            for payment in payments:
                payment_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                    and not l.reconciled
                )

                for account in (receivable_lines + payment_lines).mapped('account_id'):
                    lines_to_reconcile = (receivable_lines + payment_lines).filtered(
                        lambda l: l.account_id == account and not l.reconciled
                    )

                    if len(lines_to_reconcile) > 1:
                        lines_to_reconcile.reconcile()

    @api.onchange("journal_id")
    def _onchange_journal_reset_pay_now(self):
        # while not always it should be reseted (only if changing company) it's not so usual to set pay now first
        # and then change journal
        self.pay_now_journal_id = False

    def button_draft(self):
        self.filtered(lambda x: x.state == "posted" and x.pay_now_journal_id).write({"pay_now_journal_id": False})
        return super().button_draft()

    # def _post(self, soft=False):
    #     res = super()._post(soft=soft)
    #     self.pay_now()
    #     return res

    def _search_default_journal(self):
        if self.env.context.get("default_company_id"):
            self.env.company = self.env["res.company"].browse(self.env.context.get("default_company_id"))
        return super()._search_default_journal()
