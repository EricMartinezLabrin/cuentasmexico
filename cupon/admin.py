from django.contrib import admin
from cupon.models import Cupon, CouponRedemption


@admin.register(Cupon)
class CuponAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'status', 'price', 'duration_unit', 'duration_quantity',
        'used_count', 'max_uses', 'one_use_per_phone'
    )
    search_fields = ('name',)
    list_filter = ('status', 'duration_unit', 'one_use_per_phone')


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ('cupon', 'customer', 'phone_lada', 'phone_number', 'channel', 'redeemed_at')
    search_fields = ('cupon__name', 'customer__username', 'phone_number')
    list_filter = ('channel', 'redeemed_at')
