from django import template
import math


register = template.Library()

@register.filter()
def new_price(value, args):
    price = value-((value*args)/100)
    return math.ceil(price)

@register.filter()
def new_currency(value,args):
    return math.ceil(value/args)