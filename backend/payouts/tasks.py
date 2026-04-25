from celery import shared_task

@shared_task
def process_payout(payout_id):
    pass
