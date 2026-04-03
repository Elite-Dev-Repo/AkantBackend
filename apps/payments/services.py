"""
Payments service layer.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from .models import BankTransferPayment, Payment
from .paystack import PaystackClient
from apps.expenses.models import Debt
from apps.expenses.services import ExpenseService


class PaymentService:

    @staticmethod
    @transaction.atomic
    def initiate_payment(payer, debt_id: str) -> Payment:
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
        payment = Payment.objects.select_related("debt__group").get(reference=reference)
        if payment.status == Payment.Status.SUCCESS:
            return payment

        ps_data = PaystackClient.verify_transaction(reference)
        ps_status = ps_data.get("status")
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
        if event == "charge.success":
            reference = data.get("reference")
            if not reference:
                return
            try:
                PaymentService.verify_and_settle(reference)
            except Payment.DoesNotExist:
                pass

    @staticmethod
    @transaction.atomic
    def initiate_bank_transfer(payer, debt_id: str, note: str = "") -> BankTransferPayment:
        from apps.users.models import AccountDetails

        debt = Debt.objects.select_related("creditor", "debtor", "group").get(
            id=debt_id, is_settled=False
        )
        if debt.debtor != payer:
            raise PermissionError("Only the debtor can initiate payment.")

        account = AccountDetails.objects.filter(user=debt.creditor).first()
        if not account:
            raise ValueError(
                f"{debt.creditor.full_name} has not added their bank account details yet. "
                "Ask them to add their account details in Settings."
            )

        transfer = BankTransferPayment.objects.create(
            debt=debt,
            payer=payer,
            creditor=debt.creditor,
            account_details=account,
            amount=debt.amount,
            note=note,
        )
        return transfer

    @staticmethod
    @transaction.atomic
    def confirm_bank_transfer(transfer_id: str, requesting_user) -> BankTransferPayment:
        transfer = BankTransferPayment.objects.select_related("debt__group").get(id=transfer_id)

        if transfer.creditor != requesting_user:
            raise PermissionError("Only the creditor can confirm receipt of payment.")

        if transfer.status == BankTransferPayment.Status.CONFIRMED:
            return transfer

        transfer.status = BankTransferPayment.Status.CONFIRMED
        transfer.confirmed_at = timezone.now()
        transfer.save(update_fields=["status", "confirmed_at"])

        ExpenseService.settle_debt(str(transfer.debt_id), requesting_user)
        return transfer