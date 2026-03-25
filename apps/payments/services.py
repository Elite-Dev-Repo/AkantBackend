"""
Payments service layer.
Orchestrates Paystack calls + local Payment model updates.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from .models import Payment
from .paystack import PaystackClient
from apps.expenses.models import Debt
from apps.expenses.services import ExpenseService


class PaymentService:

    @staticmethod
    @transaction.atomic
    def initiate_payment(payer, debt_id: str) -> Payment:
        """
        Initialize a Paystack transaction for a debt.
        Returns an unsaved Payment with authorization_url.
        """
        debt = Debt.objects.select_related("creditor", "debtor", "group").get(
            id=debt_id, is_settled=False
        )

        if debt.debtor != payer:
            raise PermissionError("Only the debtor can initiate payment.")

        reference = PaystackClient.generate_reference()
        callback_url = f"{settings.FRONTEND_URL}/payments/verify?reference={reference}"

        metadata = {
            "debt_id": str(debt.id),
            "group_id": str(debt.group_id),
            "payer_id": str(payer.id),
            "recipient_id": str(debt.creditor_id),
        }

        paystack_data = PaystackClient.initialize_transaction(
            email=payer.email,
            amount_kobo=int(debt.amount * 100),
            reference=reference,
            callback_url=callback_url,
            metadata=metadata,
        )

        payment = Payment.objects.create(
            debt=debt,
            payer=payer,
            recipient=debt.creditor,
            amount=debt.amount,
            currency="NGN",
            reference=reference,
            authorization_url=paystack_data["authorization_url"],
            access_code=paystack_data.get("access_code", ""),
            metadata=metadata,
            status=Payment.Status.PENDING,
        )
        return payment

    @staticmethod
    @transaction.atomic
    def verify_and_settle(reference: str) -> Payment:
        """
        Verify a Paystack payment by reference, update Payment record,
        and settle the linked debt if successful.
        """
        payment = Payment.objects.select_related("debt__group").get(reference=reference)

        if payment.status == Payment.Status.SUCCESS:
            return payment  # idempotent

        ps_data = PaystackClient.verify_transaction(reference)

        ps_status = ps_data.get("status")  # success | failed | abandoned
        payment.paystack_id = ps_data.get("id")
        payment.channel = ps_data.get("channel", "")
        payment.paid_at = timezone.now() if ps_status == "success" else None
        payment.status = {
            "success": Payment.Status.SUCCESS,
            "failed": Payment.Status.FAILED,
            "abandoned": Payment.Status.ABANDONED,
        }.get(ps_status, Payment.Status.PENDING)
        payment.save()

        if payment.status == Payment.Status.SUCCESS and payment.debt:
            ExpenseService.settle_debt(str(payment.debt_id), payment.payer)

        return payment

    @staticmethod
    @transaction.atomic
    def handle_webhook(event: str, data: dict) -> None:
        """
        Process Paystack webhook events.
        Currently handles: charge.success
        """
        if event == "charge.success":
            reference = data.get("reference")
            if not reference:
                return
            try:
                PaymentService.verify_and_settle(reference)
            except Payment.DoesNotExist:
                # Payment not in our system — ignore
                pass
