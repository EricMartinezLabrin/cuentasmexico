from adm.models import Sale,Service
from datetime import datetime, timedelta
import operator

class Best():
    def best_sellers(actual=None,limit=None):
        start_date = datetime.now() - timedelta(days=30)
        service_name = Service.objects.all().exclude(id=actual)
        service_count = {}
        for name in service_name:
            sales = Sale.objects.filter(created_at__gte=start_date,account__account_name=name).count()
            service_count[name]=sales
        best_sellers=sorted(service_count.items(),key=operator.itemgetter(1), reverse=True)
        return best_sellers[:limit]
