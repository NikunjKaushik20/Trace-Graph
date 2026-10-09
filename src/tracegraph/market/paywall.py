import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    provider_id: str
    job_id: str
    amount_sats: int
    payment_hash: str


@dataclass(frozen=True)
class PaymentRequired:
    invoice: Invoice
    status_code: int = 402


# SHA-256 of a preimage, the way a Lightning payment hash is made
def hash_preimage(preimage: str) -> str:
    return hashlib.sha256(bytes.fromhex(preimage)).hexdigest()


# Builds the L402-style header a buyer sends back after paying: "L402 <invoice id>:<preimage>"
def authorization_header(invoice_id: str, preimage: str) -> str:
    return f"L402 {invoice_id}:{preimage}"


# Splits an L402-style header into invoice id and preimage, or None if it is malformed
def read_authorization(header: str) -> tuple[str, str] | None:
    scheme, _, token = header.partition(" ")
    invoice_id, _, preimage = token.partition(":")
    if scheme != "L402" or not invoice_id or not preimage:
        return None
    return invoice_id, preimage


class MockLightning:
    # Starts with no invoices
    def __init__(self) -> None:
        self._preimages: dict[str, str] = {}
        self._invoices: dict[str, Invoice] = {}

    # A provider asks for an invoice; only the network knows the preimage until it is paid
    def create_invoice(self, provider_id: str, job_id: str, amount_sats: int) -> Invoice:
        preimage = secrets.token_hex(32)
        invoice = Invoice(
            invoice_id=f"inv-{secrets.token_hex(6)}",
            provider_id=provider_id,
            job_id=job_id,
            amount_sats=amount_sats,
            payment_hash=hash_preimage(preimage),
        )
        self._preimages[invoice.payment_hash] = preimage
        self._invoices[invoice.invoice_id] = invoice
        return invoice

    # Paying reveals the preimage to the payer, which is the proof of payment
    def pay(self, invoice: Invoice) -> str:
        return self._preimages[invoice.payment_hash]

    # A provider checks a header proves payment of the invoice it issued for this job
    def proves_payment(self, header: str, provider_id: str, job_id: str) -> bool:
        parts = read_authorization(header)
        if parts is None:
            return False
        invoice = self._invoices.get(parts[0])
        if invoice is None or invoice.provider_id != provider_id or invoice.job_id != job_id:
            return False
        return secrets.compare_digest(hash_preimage(parts[1]), invoice.payment_hash)
