from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Avg, Case, CharField, Count, Max, Min, Q, Sum, Value, When
from django.utils import timezone

from adm.models import PaymentMethod, Sale, Service


class CRMAnalytics:
    DEFAULT_RANGE_DAYS = 30
    MAX_RANGE_DAYS = 366
    CHURN_DAYS = 45

    @classmethod
    def _currency_case(cls):
        return Case(
            When(customer__userdetail__country__iexact='Chile', then=Value('CLP')),
            When(customer__userdetail__country__iexact='CL', then=Value('CLP')),
            When(customer__userdetail__country__iexact='México', then=Value('MXN')),
            When(customer__userdetail__country__iexact='Mexico', then=Value('MXN')),
            When(customer__userdetail__country__iexact='MX', then=Value('MXN')),
            default=Value('MXN'),
            output_field=CharField(),
        )

    @classmethod
    def _currency_from_country(cls, country):
        if not country:
            return 'MXN'
        normalized = str(country).strip().lower()
        if normalized in ('chile', 'cl'):
            return 'CLP'
        if normalized in ('mexico', 'méxico', 'mx'):
            return 'MXN'
        return 'MXN'

    @staticmethod
    def _safe_int(value, default=None, min_value=None):
        if value in (None, ""):
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        if min_value is not None and parsed < min_value:
            return min_value
        return parsed

    @staticmethod
    def _safe_decimal(value, default=None):
        if value in (None, ""):
            return default
        try:
            return Decimal(str(value))
        except Exception:
            return default

    @staticmethod
    def _safe_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    @classmethod
    def parse_filters(cls, params):
        today = timezone.localdate()
        preset = (params.get("preset") or "last_30_days").strip()

        preset_map = {
            "today": 0,
            "last_7_days": 7,
            "last_30_days": 30,
            "last_90_days": 90,
            "this_month": None,
            "custom": None,
        }
        if preset not in preset_map:
            preset = "last_30_days"

        if preset == "today":
            date_from = today
            date_to = today
        elif preset in ("last_7_days", "last_30_days", "last_90_days"):
            days = preset_map[preset]
            date_to = today
            date_from = today - timedelta(days=days)
        elif preset == "this_month":
            date_to = today
            date_from = today.replace(day=1)
        else:
            date_from = cls._safe_date(params.get("date_from"))
            date_to = cls._safe_date(params.get("date_to"))
            if not date_from and not date_to:
                date_to = today
                date_from = today - timedelta(days=cls.DEFAULT_RANGE_DAYS)
            elif date_from and not date_to:
                date_to = min(today, date_from + timedelta(days=cls.DEFAULT_RANGE_DAYS))
            elif date_to and not date_from:
                date_from = date_to - timedelta(days=cls.DEFAULT_RANGE_DAYS)

        if date_from > date_to:
            date_from, date_to = date_to, date_from

        max_span_from = date_to - timedelta(days=cls.MAX_RANGE_DAYS)
        if date_from < max_span_from:
            date_from = max_span_from

        filters = {
            "preset": preset,
            "date_from": date_from,
            "date_to": date_to,
            "country": (params.get("country") or "").strip(),
            "service_id": cls._safe_int(params.get("service_id"), default=None, min_value=1),
            "seller_id": cls._safe_int(params.get("seller_id"), default=None, min_value=1),
            "payment_method_id": cls._safe_int(params.get("payment_method_id"), default=None, min_value=1),
            "sale_status": (params.get("sale_status") or "").strip().lower(),
            "amount_min": cls._safe_decimal(params.get("amount_min"), default=None),
            "amount_max": cls._safe_decimal(params.get("amount_max"), default=None),
            "customer_q": (params.get("customer_q") or "").strip(),
            "customer_type": (params.get("customer_type") or "").strip().lower(),
            "churn_sort": (params.get("churn_sort") or "desc").strip().lower(),
        }

        if filters["sale_status"] not in ("active", "inactive", "all", ""):
            filters["sale_status"] = ""
        if filters["customer_type"] not in ("new", "recurrent", "all", ""):
            filters["customer_type"] = ""
        if filters["churn_sort"] not in ("desc", "asc"):
            filters["churn_sort"] = "desc"

        if (
            filters["amount_min"] is not None
            and filters["amount_max"] is not None
            and filters["amount_min"] > filters["amount_max"]
        ):
            filters["amount_min"], filters["amount_max"] = filters["amount_max"], filters["amount_min"]

        return filters

    @staticmethod
    def _base_queryset():
        return Sale.objects.select_related(
            "customer",
            "customer__userdetail",
            "account",
            "account__account_name",
            "payment_method",
            "user_seller",
        )

    @classmethod
    def _apply_common_filters(cls, queryset, filters):
        queryset = cls._apply_non_date_filters(queryset, filters)
        queryset = queryset.filter(
            created_at__date__gte=filters["date_from"],
            created_at__date__lte=filters["date_to"],
        )

        if filters["customer_type"] in ("new", "recurrent"):
            customer_ids = list(queryset.values_list("customer_id", flat=True).distinct())
            customer_type_map = cls._build_customer_type_map(customer_ids, filters["date_from"], filters["date_to"])
            wanted_new = filters["customer_type"] == "new"
            allowed_ids = [cid for cid, is_new in customer_type_map.items() if is_new == wanted_new]
            queryset = queryset.filter(customer_id__in=allowed_ids)

        return queryset

    @classmethod
    def _apply_non_date_filters(cls, queryset, filters):

        if filters["country"]:
            queryset = queryset.filter(customer__userdetail__country__iexact=filters["country"])
        if filters["service_id"]:
            queryset = queryset.filter(account__account_name_id=filters["service_id"])
        if filters["seller_id"]:
            queryset = queryset.filter(user_seller_id=filters["seller_id"])
        if filters["payment_method_id"]:
            queryset = queryset.filter(payment_method_id=filters["payment_method_id"])
        if filters["sale_status"] == "active":
            queryset = queryset.filter(status=True)
        elif filters["sale_status"] == "inactive":
            queryset = queryset.filter(status=False)
        if filters["amount_min"] is not None:
            queryset = queryset.filter(payment_amount__gte=filters["amount_min"])
        if filters["amount_max"] is not None:
            queryset = queryset.filter(payment_amount__lte=filters["amount_max"])
        if filters["customer_q"]:
            q = filters["customer_q"]
            queryset = queryset.filter(
                Q(customer__username__icontains=q)
                | Q(customer__email__icontains=q)
                | Q(customer__userdetail__phone_number__icontains=q)
            )

        return queryset

    @classmethod
    def _build_customer_type_map(cls, customer_ids, date_from, date_to):
        if not customer_ids:
            return {}
        first_sales = (
            Sale.objects.filter(customer_id__in=customer_ids)
            .values("customer_id")
            .annotate(first_sale=Min("created_at"))
        )
        result = {}
        for item in first_sales:
            first_date = timezone.localtime(item["first_sale"]).date() if item["first_sale"] else None
            result[item["customer_id"]] = bool(first_date and date_from <= first_date <= date_to)
        return result

    @classmethod
    def get_filtered_sales(cls, params):
        filters = cls.parse_filters(params)
        queryset = cls._apply_common_filters(cls._base_queryset(), filters)
        return queryset, filters

    @staticmethod
    def _percentage(part, total):
        if not total:
            return 0
        return round((part / total) * 100, 2)

    @classmethod
    def get_kpis(cls, sales_qs):
        base = sales_qs.aggregate(
            total_sales=Count("id"),
            unique_customers=Count("customer", distinct=True),
        )

        total_sales = base["total_sales"] or 0
        unique_customers = base["unique_customers"] or 0

        customer_repeat = (
            sales_qs.values("customer_id")
            .annotate(total=Count("id"))
            .filter(total__gte=2)
            .count()
        )
        repeat_rate = cls._percentage(customer_repeat, unique_customers)

        revenue_by_currency = (
            sales_qs.annotate(currency_code=cls._currency_case())
            .values('currency_code')
            .annotate(total_revenue=Sum('payment_amount'), avg_ticket=Avg('payment_amount'))
        )
        currency_totals = {
            'MXN': {'total_revenue': 0, 'avg_ticket': 0.0},
            'CLP': {'total_revenue': 0, 'avg_ticket': 0.0},
        }
        for row in revenue_by_currency:
            code = row['currency_code'] or 'MXN'
            currency_totals[code] = {
                'total_revenue': int(row['total_revenue'] or 0),
                'avg_ticket': float(round(row['avg_ticket'] or 0, 2)),
            }

        return {
            "total_sales": total_sales,
            "unique_customers": unique_customers,
            "repeat_customers": customer_repeat,
            "repeat_rate": repeat_rate,
            "revenue_mxn": currency_totals['MXN']['total_revenue'],
            "revenue_clp": currency_totals['CLP']['total_revenue'],
            "avg_ticket_mxn": currency_totals['MXN']['avg_ticket'],
            "avg_ticket_clp": currency_totals['CLP']['avg_ticket'],
        }

    @classmethod
    def get_top_customers(cls, sales_qs, limit=50):
        rows = (
            sales_qs.values(
                "customer_id",
                "customer__username",
                "customer__email",
                "customer__userdetail__phone_number",
                "customer__userdetail__country",
            )
            .annotate(
                total_revenue=Sum("payment_amount"),
                total_orders=Count("id"),
                avg_ticket=Avg("payment_amount"),
                last_purchase=Max("created_at"),
            )
            .order_by("-total_revenue", "-total_orders")[:limit]
        )

        result = []
        for row in rows:
            result.append(
                {
                    "customer_id": row["customer_id"],
                    "username": row["customer__username"] or "",
                    "email": row["customer__email"] or "",
                    "phone": row["customer__userdetail__phone_number"] or "",
                    "country": row["customer__userdetail__country"] or "",
                    "currency": cls._currency_from_country(row["customer__userdetail__country"]),
                    "total_revenue": int(row["total_revenue"] or 0),
                    "total_orders": row["total_orders"] or 0,
                    "avg_ticket": float(round(row["avg_ticket"] or 0, 2)),
                    "last_purchase": row["last_purchase"],
                }
            )
        return result

    @classmethod
    def get_top_products(cls, sales_qs, limit=50):
        totals_by_currency = (
            sales_qs.annotate(currency_code=cls._currency_case())
            .values('currency_code')
            .annotate(total=Sum('payment_amount'))
        )
        totals_map = {row['currency_code']: int(row['total'] or 0) for row in totals_by_currency}
        rows = (
            sales_qs.annotate(currency_code=cls._currency_case())
            .values("account__account_name_id", "account__account_name__description", "currency_code")
            .annotate(total_revenue=Sum("payment_amount"), total_orders=Count("id"))
            .order_by("-total_revenue", "-total_orders")[:limit]
        )
        result = []
        for row in rows:
            revenue = int(row["total_revenue"] or 0)
            result.append(
                {
                    "service_id": row["account__account_name_id"],
                    "service": row["account__account_name__description"] or "Sin servicio",
                    "currency": row["currency_code"] or "MXN",
                    "total_revenue": revenue,
                    "total_orders": row["total_orders"] or 0,
                    "share": cls._percentage(revenue, totals_map.get(row["currency_code"], 0)),
                }
            )
        return result

    @classmethod
    def get_sales_trend(cls, sales_qs):
        rows = (
            sales_qs.annotate(currency_code=cls._currency_case())
            .values("created_at__date", "currency_code")
            .annotate(total_revenue=Sum("payment_amount"), total_orders=Count("id"))
            .order_by("created_at__date", "currency_code")
        )
        grouped = defaultdict(lambda: {"revenue_mxn": 0, "revenue_clp": 0, "total_orders": 0})
        for row in rows:
            date_key = row["created_at__date"]
            currency = row["currency_code"] or "MXN"
            revenue = int(row["total_revenue"] or 0)
            if currency == "CLP":
                grouped[date_key]["revenue_clp"] += revenue
            else:
                grouped[date_key]["revenue_mxn"] += revenue
            grouped[date_key]["total_orders"] += row["total_orders"] or 0

        result = []
        for date_key in sorted(grouped.keys()):
            result.append({
                "date": date_key,
                "revenue_mxn": grouped[date_key]["revenue_mxn"],
                "revenue_clp": grouped[date_key]["revenue_clp"],
                "total_orders": grouped[date_key]["total_orders"],
            })
        return result

    @classmethod
    def get_churn_customers(cls, filters, limit=200):
        now = timezone.now()
        churn_threshold = now - timedelta(days=cls.CHURN_DAYS)

        # Para churn no usamos el rango de fechas del dashboard en la selección base,
        # porque eso oculta clientes antiguos que precisamente queremos detectar.
        all_sales = cls._apply_non_date_filters(cls._base_queryset(), filters)

        candidate_ids = list(all_sales.values_list("customer_id", flat=True).distinct())
        if not candidate_ids:
            return []

        churn_order = "last_purchase" if filters.get("churn_sort", "desc") == "desc" else "-last_purchase"
        latest_sales = (
            Sale.objects.filter(customer_id__in=candidate_ids)
            .values("customer_id")
            .annotate(last_purchase=Max("created_at"), total_revenue=Sum("payment_amount"), total_orders=Count("id"))
            .filter(last_purchase__lt=churn_threshold)
            .order_by(churn_order)
        )

        last_service_map = {}
        raw_last_sales = (
            Sale.objects.filter(customer_id__in=[x["customer_id"] for x in latest_sales])
            .select_related("account__account_name")
            .order_by("customer_id", "-created_at")
        )
        seen = set()
        for sale in raw_last_sales:
            if sale.customer_id in seen:
                continue
            seen.add(sale.customer_id)
            last_service_map[sale.customer_id] = sale.account.account_name.description if sale.account_id else ""

        user_map = {
            user.id: user
            for user in User.objects.select_related("userdetail").filter(id__in=[x["customer_id"] for x in latest_sales])
        }

        result = []
        for row in latest_sales[:limit]:
            customer_id = row["customer_id"]
            user = user_map.get(customer_id)
            if not user:
                continue
            days_inactive = (now - row["last_purchase"]).days if row["last_purchase"] else 0
            result.append(
                {
                    "customer_id": customer_id,
                    "username": user.username or "",
                    "email": user.email or "",
                    "phone": getattr(getattr(user, "userdetail", None), "phone_number", "") or "",
                    "country": getattr(getattr(user, "userdetail", None), "country", "") or "",
                    "currency": cls._currency_from_country(getattr(getattr(user, "userdetail", None), "country", "")),
                    "last_purchase": row["last_purchase"],
                    "days_inactive": days_inactive,
                    "total_revenue": int(row["total_revenue"] or 0),
                    "total_orders": row["total_orders"] or 0,
                    "last_service": last_service_map.get(customer_id, ""),
                }
            )
        return result

    @classmethod
    def get_recovered_customers(cls, filters, limit=500):
        """
        Cliente recuperado:
        - Tiene una compra en el rango seleccionado.
        - Esa compra ocurre 45+ días después de su compra inmediatamente anterior.
        """
        date_from = filters["date_from"]
        date_to = filters["date_to"]

        all_sales = (
            cls._apply_non_date_filters(cls._base_queryset(), filters)
            .order_by("customer_id", "created_at", "id")
        )

        last_sale_by_customer = {}
        recovered_events = []

        for sale in all_sales:
            previous_sale = last_sale_by_customer.get(sale.customer_id)
            if previous_sale:
                gap_days = (sale.created_at - previous_sale.created_at).days
                if (
                    gap_days >= cls.CHURN_DAYS
                    and date_from <= sale.created_at.date() <= date_to
                ):
                    country = getattr(getattr(sale.customer, "userdetail", None), "country", "") or ""
                    recovered_events.append({
                        "customer_id": sale.customer_id,
                        "username": sale.customer.username or "",
                        "email": sale.customer.email or "",
                        "phone": getattr(getattr(sale.customer, "userdetail", None), "phone_number", "") or "",
                        "country": country,
                        "currency": cls._currency_from_country(country),
                        "recovery_date": sale.created_at,
                        "days_inactive_before_recovery": gap_days,
                        "service": sale.account.account_name.description if sale.account_id else "",
                        "amount": int(sale.payment_amount or 0),
                    })
            last_sale_by_customer[sale.customer_id] = sale

        # Mostrar primero recuperaciones más recientes
        recovered_events.sort(key=lambda x: x["recovery_date"], reverse=True)
        return recovered_events[:limit]

    @classmethod
    def get_recovered_stats(cls, recovered_customers):
        stats = {
            "count": len(recovered_customers),
            "revenue_mxn": 0,
            "revenue_clp": 0,
        }
        for row in recovered_customers:
            if row["currency"] == "CLP":
                stats["revenue_clp"] += int(row["amount"] or 0)
            else:
                stats["revenue_mxn"] += int(row["amount"] or 0)
        return stats

    @classmethod
    def get_churn_products(cls, churn_customers):
        if not churn_customers:
            return []
        customer_ids = [row["customer_id"] for row in churn_customers]
        rows = (
            Sale.objects.filter(customer_id__in=customer_ids)
            .annotate(currency_code=cls._currency_case())
            .values("account__account_name__description", "currency_code")
            .annotate(total_orders=Count("id"), total_revenue=Sum("payment_amount"))
            .order_by("-total_orders", "-total_revenue")
        )
        return [
            {
                "service": row["account__account_name__description"] or "Sin servicio",
                "currency": row["currency_code"] or "MXN",
                "total_orders": row["total_orders"] or 0,
                "total_revenue": int(row["total_revenue"] or 0),
            }
            for row in rows
        ]

    @classmethod
    def get_churn_customer_product_breakdown(cls, churn_customers):
        if not churn_customers:
            return []

        customer_ids = [row["customer_id"] for row in churn_customers]
        rows = (
            Sale.objects.filter(customer_id__in=customer_ids)
            .annotate(currency_code=cls._currency_case())
            .values("customer_id", "account__account_name__description", "currency_code")
            .annotate(total_orders=Count("id"), total_revenue=Sum("payment_amount"))
            .order_by("customer_id", "-total_orders", "-total_revenue")
        )

        grouped = defaultdict(list)
        for row in rows:
            grouped[row["customer_id"]].append(
                {
                    "service": row["account__account_name__description"] or "Sin servicio",
                    "currency": row["currency_code"] or "MXN",
                    "total_orders": row["total_orders"] or 0,
                    "total_revenue": int(row["total_revenue"] or 0),
                }
            )

        output = []
        for customer in churn_customers:
            output.append(
                {
                    "customer": customer,
                    "products": grouped.get(customer["customer_id"], []),
                }
            )
        return output

    @classmethod
    def get_filter_options(cls):
        countries = (
            Sale.objects.exclude(customer__userdetail__country__isnull=True)
            .exclude(customer__userdetail__country="")
            .values_list("customer__userdetail__country", flat=True)
            .distinct()
            .order_by("customer__userdetail__country")
        )

        return {
            "countries": list(countries),
            "services": Service.objects.filter(status=True).order_by("description"),
            "sellers": User.objects.filter(Worker__isnull=False).distinct().order_by("username"),
            "payment_methods": PaymentMethod.objects.all().order_by("description"),
        }

    @classmethod
    def get_cohort_summary(cls, sales_qs):
        customer_counts = Counter()
        repeat_counts = Counter()

        rows = (
            sales_qs.values("customer_id", "created_at__year", "created_at__month")
            .annotate(total=Count("id"))
            .order_by("created_at__year", "created_at__month")
        )
        for row in rows:
            key = f"{row['created_at__year']}-{row['created_at__month']:02d}"
            customer_counts[key] += 1
            if row["total"] >= 2:
                repeat_counts[key] += 1

        keys = sorted(customer_counts.keys())
        return [
            {
                "period": key,
                "customers": customer_counts[key],
                "repeat_customers": repeat_counts[key],
                "repeat_rate": cls._percentage(repeat_counts[key], customer_counts[key]),
            }
            for key in keys
        ]

    @classmethod
    def build_dashboard_data(cls, params):
        sales_qs, filters = cls.get_filtered_sales(params)
        top_customers = cls.get_top_customers(sales_qs)
        top_products = cls.get_top_products(sales_qs)
        churn_customers = cls.get_churn_customers(filters)
        churn_products = cls.get_churn_products(churn_customers)
        churn_breakdown = cls.get_churn_customer_product_breakdown(churn_customers)
        recovered_customers = cls.get_recovered_customers(filters)
        recovered_stats = cls.get_recovered_stats(recovered_customers)

        return {
            "filters": filters,
            "kpis": cls.get_kpis(sales_qs),
            "top_customers": top_customers,
            "top_products": top_products,
            "sales_trend": cls.get_sales_trend(sales_qs),
            "cohort_summary": cls.get_cohort_summary(sales_qs),
            "churn_customers": churn_customers,
            "churn_products": churn_products,
            "churn_breakdown": churn_breakdown,
            "recovered_customers": recovered_customers,
            "recovered_stats": recovered_stats,
            "options": cls.get_filter_options(),
        }
