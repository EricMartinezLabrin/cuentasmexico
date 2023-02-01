from adm.models import Account, Service, UserDetail,Bank,PaymentMethod,Sale,Status, Business
from cupon.models import Cupon
from django.contrib.auth.models import User
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from django.shortcuts import render,redirect
from django.urls import reverse,reverse_lazy
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from adm.functions.send_email import Email


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
        created_at = request.POST.get('created_at')
        how_many_acc = len(service)
        price_each = int(int(price) / how_many_acc)
        for s in service:
            acc = Account.objects.get(pk=s)
            if acc.customer == None:
                #create sale
                sale = Sale.objects.create(
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

                #update date
                sale.created_at = created_at
                sale.save()

                if not customer.email == 'example@example.com':
                    Email.email_passwords(request,customer.email,(sale,))
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
            cupon.status = False
            cupon.save()

            if customer.email != 'example@example.com':
                Email.email_passwords(request,customer.email,(sale,))

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

        if customer.email != 'example@example.com':
            Email.email_passwords(request,customer.email,(new_sale,))

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
        old_acc.customer=None
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

        if old_sale.customer.email != 'example@example.com':
            Email.email_passwords(request,old_sale.customer.email,(new_sale,))

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
                    'message':None,
                    'copy':None,
                    'active':Sales.customer_sales_active(customer),
                    'inactive':Sales.customer_sales_inactive(customer)
            }
            return render(request,'adm/sale.html',my_dict)

    def search_better_acc(service_id,exp, code=None):
        if not Cupon.objects.get(name=code).customer or code == None:
            print(Cupon.objects.get(name=code).customer)
            try:
                service = Service.objects.get(pk=service_id)
            except Service.DoesNotExist:
                return False , "La cuenta seleccionada no existe. Porfavor contactarse al whats app +521 833 535 5863."
            esta = None
            exp1 = f'{exp.date()} 00:00:00'
            exp2 = f'{exp.date()} 23:59:59'
            try:
                account = Sale.objects.filter(account__account_name=service,expiration_date__gte=exp1,expiration_date__lte=exp2,status=True).order_by('expiration_date')
                if account.count() == 0:
                    raise Sale.DoesNotExist
                else:
                    for a in account:
                        selected = Account.objects.filter(account_name=service,email=a.account.email,status=True, customer=None)
                        if selected.count() > 0:
                            return selected[0]
                        else:
                            raise Sale.DoesNotExist
            except Sale.DoesNotExist:
                #find empty accounts
                empty = Account.objects.filter(account_name=service, status=True, customer=None)
                if empty.count()==0:
                    return False, "No hay cuentas disponibles, porfavor comunicate al whats app +521 833 535 5863"
                for e in empty:
                    q = Account.objects.filter(email = e.email, account_name = service, status=True, customer=None)
                    if q.count() == service.perfil_quantity:
                        return True,q[0]
                if not esta:
                    account = Sale.objects.filter(account__account_name=service,expiration_date__gte=exp1,status=True).order_by('expiration_date')
                    if account.count() > 0:
                        for a in account:
                            acc = Account.objects.filter(email=a.account.email,password=a.account.password,account_name=a.account.account_name,customer=None,status=True)
                            if acc.count() > 0:
                                return True,acc[0]
                    elif account.count() < 0:
                        account = Sale.objects.filter(account__account_name=service,expiration_date__lte=exp1,status=True).order_by('-expiration_date')
                        if account.count() > 0:
                            for a in account:
                                acc = Account.objects.filter(email=a.account.email,password=a.account.password,account_name=a.account.account_name,customer=None,status=True)
                                if acc.count() > 0:
                                    return True,acc[0]
                    else:
                        return False, "No hay cuentas disponibles, porfavor comunicate al whats app +521 833 535 5863"
        else:
            return False, "El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo."

    def redeem(request,acc,code,customer_id):
        cupon = Cupon.objects.get(name=code)
        service = acc
        price = cupon.price
        duration = cupon.long
        ticket = cupon.name
        customer = User.objects.get(pk=customer_id)   
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
                business = Business.objects.get(pk=1),
                user_seller = User.objects.get(pk=1),
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
            service.modified_by=User.objects.get(pk=1)
            service.save()

            #Update Cupon
            cupon.used_at = datetime.now()
            cupon.customer = customer
            cupon.seller = User.objects.get(pk=1)
            cupon.order = sale
            cupon.status_sale = True
            cupon.status = False
            cupon.save()

            if customer.email != 'example@example.com':
                Email.email_passwords(request,customer.email,(sale,))

        return True

    def redeem_renew(request,acc,code,customer_id):
        cupon = Cupon.objects.get(name=code)
        if cupon.status == True:
            price = cupon.price
            duration = cupon.long
            ticket = code
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
            customer = User.objects.get(pk=customer_id)
            old_sale = Sale.objects.get(account_id=acc,status=True)
            old_acc = Account.objects.get(pk=old_sale.account.id)
            if old_sale.expiration_date.date() >= datetime.now().date():
                exp_date = old_sale.expiration_date.date() + relativedelta(months=duration)
            else:
                exp_date = datetime.now() + relativedelta(months=duration)
            
            #create sale
            new_sale = Sale.objects.create(
                business = Business.objects.get(pk=1),
                user_seller = User.objects.get(pk=1),
                bank = bank_selected,
                customer = customer,
                account = acc,
                status = True,
                payment_method = payment_used,
                expiration_date = exp_date,
                payment_amount = price,
                invoice =ticket,
                old_acc=old_acc.id
            )
            #update account
            acc.modified_by=User.objects.get(pk=1)
            acc.save()

            new_sale_id = new_sale.id

            #deprecate old sale
            old_sale.status = False
            old_sale.old_sale = new_sale_id
            old_sale.save()

            #Update Cupon
            cupon.used_at = datetime.now()
            cupon.customer = customer
            cupon.seller = User.objects.get(pk=1)
            cupon.order = new_sale
            cupon.status_sale = True
            cupon.status = False
            cupon.save()

            if customer.email != 'example@example.com':
                Email.email_passwords(request,customer.email,(new_sale,))

            return True, acc
        else:
            return False, "El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo."





