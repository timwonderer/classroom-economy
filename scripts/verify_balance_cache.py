from app import create_app, db
from app.models import LedgerBalanceSnapshot, Transaction, TransactionStatus

app = create_app()
with app.app_context():
    print("--- Verifying Ledger Migration ---")
    
    bc_count = LedgerBalanceSnapshot.query.count()
    print(f"LedgerBalanceSnapshot rows: {bc_count}")
    
    tx_count = Transaction.query.count()
    print(f"Total Transactions: {tx_count}")
    
    posted_tx_count = Transaction.query.filter(Transaction.status == TransactionStatus.POSTED).count()
    print(f"Posted Transactions: {posted_tx_count}")
    
    null_cents = Transaction.query.filter(Transaction.amount_cents.is_(None)).count()
    print(f"Transactions with NULL amount_cents: {null_cents}")
    
    if tx_count > 0:
        sample = Transaction.query.first()
        print(f"Sample Transaction: ID={sample.id}, Amount={sample.amount}, Cents={sample.amount_cents}, Status={sample.status}")
        
    print("--- Verification Complete ---")
