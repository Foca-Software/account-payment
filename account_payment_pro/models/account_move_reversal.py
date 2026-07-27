from odoo import models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def reverse_moves(self, is_modify=False):
        """Al revertir/crear una Nota de Crédito, el flujo normal de Odoo
        toca to_pay_move_line_ids del account.payment relacionado, lo que
        puede disparar un falso positivo en la constraint
        _check_to_pay_move_line_ids_payment_group de account_payment_group
        (ver SW-2040). Exceptuamos ese chequeo durante este flujo legítimo.
        """
        return super(
            AccountMoveReversal,
            self.with_context(skip_payment_group_lines_check=True),
        ).reverse_moves(is_modify)
