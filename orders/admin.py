from django.contrib import admin
from .models import Order, OrderItem


# Register your models here.
class OrderItemInline(admin.StackedInline):
    model: type[OrderItem] = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'created_at')
    list_display_links = ('status',)
    inlines: list[type[OrderItemInline]] = [OrderItemInline]
