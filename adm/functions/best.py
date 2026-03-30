from adm.models import Sale, Service
from datetime import datetime, timedelta
from django.db.models import Count

class Best():
    def best_sellers(actual=None, limit=None):
        start_date = datetime.now() - timedelta(days=30)
        services = list(Service.objects.exclude(id=actual))
        if not services:
            return []

        service_ids = [service.id for service in services]
        sales_by_service = {
            row['account__account_name']: row['total']
            for row in (
                Sale.objects.filter(
                    created_at__gte=start_date,
                    account__account_name_id__in=service_ids,
                )
                .values('account__account_name')
                .annotate(total=Count('id'))
            )
        }

        best_sellers = sorted(
            [(service, sales_by_service.get(service.id, 0)) for service in services],
            key=lambda item: item[1],
            reverse=True,
        )
        return best_sellers[:limit]
