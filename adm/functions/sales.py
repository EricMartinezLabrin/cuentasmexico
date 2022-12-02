from adm.models import Account, Service, UserDetail,Bank,PaymentMethod,Sale,Status, Business
from cupon.models import Cupon
from django.contrib.auth.models import User
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.shortcuts import render,redirect
from django.urls import reverse,reverse_lazy
from django.db import IntegrityError
from django.http import HttpResponseRedirect


class Sales():

    def availables():
        """
        Show quantity of all available accounts
        """
        #Get Account Names
        serv = Service.objects.filter(status=True)
        result = {}
        # account as a and service as sev
        for a in serv:
            result[a.description] = Account.objects.filter(status=True, customer=None, account_name=a).count()
        return result,serv

    def is_email(request,customer):
        cm = customer.replace(" ","")

        if cm.isnumeric():
            if len(cm) > 13:       
                raise NameError
            else:
                try:
                    pk = UserDetail.objects.get(phone_number=cm).user
                    return User.objects.get(pk=pk.id)
                except UserDetail.DoesNotExist:
                    try:
                        user = User.objects.get(username=cm)
                        user_detail = UserDetail.objects.create(business=request.user.userdetail.business,user=user,phone_number=cm,lada=0,country="??")
                        return user_detail             
                    except User.DoesNotExist:           
                        return 'phone'          
                
        else:
            if '@' in cm:
                try:
                    user = User.objects.get(email=cm)
                    user_detail = UserDetail.objects.get(user=user)
                    return user
                except User.DoesNotExist:
                    return 'email'
                except UserDetail.DoesNotExist:
                    user_detail = UserDetail.objects.create(business=request.user.userdetail.business,user=user,phone_number=0,lada=0,country="??")
                    return user_detail
            else:
                raise TypeError

    def new_sale(request):
        service = request.POST.getlist('serv')
        price = request.POST.get('price')
        duration = int(request.POST.get('duration'))
        ticket = request.POST.get('comp')
        bank_selected = Bank.objects.get(pk=request.POST.get('bank'))
        payment_used = PaymentMethod.objects.get(pk=request.POST.get('method'))
        customer = User.objects.get(pk=request.POST.get('customer'))
        how_many_acc = len(service)
        price_each = int(int(price) / how_many_acc)
        for s in service:
            acc = Account.objects.get(pk=s)
            if acc.customer == None:
                #create sale
                Sale.objects.create(
                    business = request.user.userdetail.business,
                    user_seller = request.user,
                    bank = bank_selected,
                    customer = customer,
                    account = acc,
                    status = True,
                    payment_method = payment_used,
                    expiration_date = datetime.now() + relativedelta(months=duration),
                    payment_amount = price_each,
                    invoice =ticket
                )
                #update account
                acc.customer=User.objects.get(pk=customer.id)
                acc.modified_by=request.user
                acc.save()
            else:
                continue
        return True

    def cupon_sale(request):
        c=request.POST.get('code').lower()
        cupon = Cupon.objects.get(name=request.POST.get('code').lower())
        service = Account.objects.get(pk=request.POST.get('serv'))
        price = cupon.price
        duration = cupon.long
        ticket = cupon.name
        customer = User.objects.get(pk=request.POST.get('customer'))   
        try:
            bank_selected = Bank.objects.get(bank_name='Shops')
        except Bank.DoesNotExist:
            bank_selected = Bank.objects.create(
                business = Business.objects.get(pk=1),
                bank_name = 'Shops',
                headline = 'Cuentas Mexico',
                card_number = '0',
                clabe = '0',
            )
        try:
            payment_used = PaymentMethod.objects.get(description='Codigo')
        except PaymentMethod.DoesNotExist:
            payment_used = PaymentMethod.objects.create(description='Codigo')

        try:
            sale = Sale.objects.get(invoice=ticket)
        except Sale.DoesNotExist:
            #create sale
            sale = Sale.objects.create(
                business = request.user.userdetail.business,
                user_seller = request.user,
                bank = bank_selected,
                customer = customer,
                account = service,
                status = True,
                payment_method = payment_used,
                expiration_date = datetime.now() + relativedelta(months=duration),
                payment_amount = price,
                invoice = ticket
            )
            #update account
            service.customer=customer
            service.modified_by=request.user
            service.save()

            #Update Cupon
            cupon.used_at = datetime.now()
            cupon.customer = customer
            cupon.seller = request.user
            cupon.order = sale
            cupon.status_sale = True
            cupon.save()

        return True

    def renew_sale(request,old):
        service = request.POST.get('serv')
        price = request.POST.get('price')
        duration = int(request.POST.get('duration'))
        ticket = request.POST.get('comp')
        bank_selected = Bank.objects.get(pk=request.POST.get('bank'))
        payment_used = PaymentMethod.objects.get(pk=request.POST.get('method'))
        customer = User.objects.get(pk=request.POST.get('customer'))
        old_sale = Sale.objects.get(pk=old)
        acc = Account.objects.get(pk=old_sale.account.id)
        if Sale.objects.get(pk=old).expiration_date.date() >= datetime.now().date():
            exp_date = old_sale.expiration_date.date() + relativedelta(months=duration)
        else:
            exp_date = datetime.now() + relativedelta(months=duration)
        
        #create sale
        new_sale = Sale.objects.create(
            business = request.user.userdetail.business,
            user_seller = request.user,
            bank = bank_selected,
            customer = customer,
            account = acc,
            status = True,
            payment_method = payment_used,
            expiration_date = exp_date,
            payment_amount = price,
            invoice =ticket,
            old_acc=old
        )
        #update account
        acc.modified_by=request.user
        acc.save()

        new_sale_id = new_sale.id

        #deprecate old sale
        old_sale.status = False
        old_sale.old_sale = new_sale_id
        old_sale.save()

        return True

    def change_sale(request):
        sale = request.POST.get('sale')
        service = request.POST.get('serv')
        price = 0
        ticket = 'Cambio'
        try:
            payment_used = PaymentMethod.objects.get(description='Cambio')
        except PaymentMethod.DoesNotExist:
            payment_used=None

        #suspend old Sale
        old_sale = Sale.objects.get(pk=sale)
        old_sale.status = False
        old_sale.save()

        #suspend old acc
        old_acc = Account.objects.get(pk=old_sale.account.id)
        old_acc.status = False
        old_acc.save()

        acc = Account.objects.get(pk=service)
        #create sale
        new_sale = Sale.objects.create(
            business = request.user.userdetail.business,
            user_seller = request.user,
            customer = old_sale.customer,
            account = acc,
            status = True,
            payment_method = payment_used,
            expiration_date = old_sale.expiration_date,
            payment_amount = price,
            invoice =ticket
        )
        new_sale_id = new_sale.id
        old_sale.old_acc = new_sale_id
        old_sale.save()
        #update account
        acc.customer=old_sale.customer
        acc.modified_by=request.user
        acc.save()

        return True

    def customer_sales_active(customer):
        active = Sale.objects.filter(
            customer = customer,
            status = True
        )
        return active

    def customer_sales_inactive(customer):
        inactive = Sale.objects.filter(
            customer = customer,
            status = False
        )
        return inactive

    def render_view(request,customer=None,message=None,copy=None):
        
        if customer == None:
            my_dict = {
                    'availables': Sales.availables()[0],
                    'message':message,
                    'active':Sales.customer_sales_active(customer),
                    'inactive':Sales.customer_sales_inactive(customer)
            }
            return render(request,'adm/sale.html',my_dict)
        else:
            try:
                customer = User.objects.get(pk=customer)
            except TypeError:
                pass
            my_dict = {
                    'availables': Sales.availables()[0],
                    'customer':customer,
                    'message':message,
                    'copy':copy,
                    'active':Sales.customer_sales_active(customer),
                    'inactive':Sales.customer_sales_inactive(customer)
            }
            return render(request,'adm/sale.html',my_dict)




