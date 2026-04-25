from django.core.management.base import BaseCommand
from merchants.models import Merchant
from ledger.models import LedgerEntry

class Command(BaseCommand):
    help = 'Seed the database with merchants and ledger entries'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Seeding database...'))

        merchants_data = [
            {
                "name": "Merchant A",
                "email": "merchant_a@example.com",
                "entries": [20000, 15000, 15000]
            },
            {
                "name": "Merchant B",
                "email": "merchant_b@example.com",
                "entries": [60000, 40000]
            },
            {
                "name": "Merchant C",
                "email": "merchant_c@example.com",
                "entries": [50000, 50000, 50000, 50000]
            }
        ]

        invoice_counter = 1000

        for data in merchants_data:
            merchant, created = Merchant.objects.get_or_create(
                email=data["email"],
                defaults={"name": data["name"]}
            )

            if created:
                for amount in data["entries"]:
                    invoice_counter += 1
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        amount_paise=amount,
                        entry_type=LedgerEntry.EntryType.CREDIT,
                        description=f'Payment from client - Invoice #{invoice_counter}'
                    )
                self.stdout.write(self.style.SUCCESS(f'Created {merchant.name} and seeded ledger entries.'))
            else:
                self.stdout.write(self.style.SUCCESS(f'{merchant.name} already exists. Skipping ledger seeding.'))

            self.stdout.write(self.style.WARNING(f"ID: {merchant.id}"))

        self.stdout.write(self.style.SUCCESS('Seeding complete!'))
