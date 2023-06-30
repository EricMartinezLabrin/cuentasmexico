from adm.models import Account, Service, UserDetail, Bank, PaymentMethod, Sale, Status, Business, Credits
from api.functions.notifications import send_push_notification
from cupon.models import Cupon
from django.contrib.auth.models import User
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from adm.functions.send_email import Email
from django.utils import timezone
from datetime import timedelta
from traceback import format_exc


class Sales():

    def availables():
        """
        Show quantity of all available accounts
        """
        # Get Account Names
        serv = Service.objects.filter(status=True)
        result = {}
        # account as a and service as sev
        for a in serv:
            result[a.description] = Account.objects.filter(
                status=True, customer=None, account_name=a).count()
        return result, serv

    def is_email(request, customer):
        cm = customer.replace(" ", "")

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
                        user_detail = UserDetail.objects.create(
                            business=request.user.userdetail.business, user=user, phone_number=cm, lada=0, country="??")
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
                    user_detail = UserDetail.objects.create(
                        business=request.user.userdetail.business, user=user, phone_number=0, lada=0, country="??")
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
        if int(price) == 0:
            price_each = 0
        else:
            price_each = int(int(price) / how_many_acc)
        for s in service:
            acc = Account.objects.get(pk=s)
            if acc.customer == None:
                # create sale
                sale = Sale.objects.create(
                    business=request.user.userdetail.business,
                    user_seller=request.user,
                    bank=bank_selected,
                    customer=customer,
                    account=acc,
                    status=True,
                    payment_method=payment_used,
                    expiration_date=timezone.now() + relativedelta(months=duration),
                    payment_amount=price_each,
                    invoice=ticket
                )
                # update account
                acc.customer = User.objects.get(pk=customer.id)
                acc.modified_by = request.user
                acc.save()

                # update date
                sale.created_at = created_at
                sale.save()
                try:
                    token = UserDetail.objects.get(user=customer).token
                    title = f"Muchas Gracias por tu compra"
                    body = f"Para ver las claves de tu cuenta {acc.account_name.description} da click en el botón de abajo o visita la seccion Mi Cuenta"
                    url = "MyAccount"
                    notification = send_push_notification(
                        token, title, body, url)
                except:
                    pass

                if not customer.email == 'example@example.com':
                    Email.email_passwords(request, customer.email, (sale,))
            else:
                continue
        return True

    def cupon_sale(request=None, service=None, price=None, duration=None, ticket=None, customer_id=None, bank_name='Web', payment_used="Saldo Distribuidor"):
        if request:
            c = request.POST.get('code')
        else:
            c = None

        if customer_id:
            customer = User.objects.get(pk=customer_id)
        elif request.POST.get('customer'):
            customer = User.objects.get(pk=request.POST.get('customer'))
        else:
            customer = User.objects.get(pk=request.user.id)

        if c:
            cupon = Cupon.objects.get(name=request.POST.get('code').lower())
            service = Account.objects.get(pk=request.POST.get('serv'))
            price = cupon.price
            duration = cupon.long
            ticket = cupon.name
            bank_name = 'Shops'
            payment_used = 'Codigo'

            # Update Cupon
            cupon.used_at = timezone.now()
            cupon.customer = customer
            cupon.seller = request.user
            cupon.status_sale = True
            cupon.status = False
            cupon.save()

        try:
            bank_selected = Bank.objects.get(bank_name=bank_name)
        except Bank.DoesNotExist:
            bank_selected = Bank.objects.create(
                business=Business.objects.get(pk=1),
                bank_name=bank_name,
                headline='Cuentas Mexico',
                card_number='0',
                clabe='0',
            )
        try:
            payment_used = PaymentMethod.objects.get(description=payment_used)
        except PaymentMethod.DoesNotExist:
            payment_used = PaymentMethod.objects.create(
                description=payment_used)

        try:
            sale = Sale.objects.get(invoice=ticket)
            if ticket == 'Web':
                raise Sale.DoesNotExist
        except Sale.MultipleObjectsReturned:
            if ticket == 'Web':
                # create sale
                sale = Sale.objects.create(
                    business=Business.objects.get(pk=1),
                    user_seller=customer,
                    bank=bank_selected,
                    customer=customer,
                    account=service,
                    status=True,
                    payment_method=payment_used,
                    expiration_date=timezone.now() + timedelta(days=30*duration),
                    payment_amount=price,
                    invoice=ticket
                )
                # update account
                service.customer = customer
                service.modified_by = customer
                service.save()

                try:
                    token = UserDetail.objects.get(user=customer).token
                    title = f"Muchas Gracias por tu compra"
                    body = f"Visita la sección Mi Cuenta para ver las nuevas claves"
                    url = "MyAccount"

                    notification = send_push_notification(
                        token, title, body, url)
                except:
                    pass

                if customer.email != 'example@example.com':
                    Email.email_passwords(request, customer.email, (sale,))

            return True, sale
        except Sale.DoesNotExist:
            # create sale
            sale = Sale.objects.create(
                business=Business.objects.get(pk=1),
                user_seller=customer,
                bank=bank_selected,
                customer=customer,
                account=service,
                status=True,
                payment_method=payment_used,
                expiration_date=timezone.now() + timedelta(days=30*duration),
                payment_amount=price,
                invoice=ticket
            )
            # update account
            service.customer = customer
            service.modified_by = request.user
            service.save()

            cupon.order = sale
            cupon.save()

            try:
                token = UserDetail.objects.get(user=customer).token
                title = f"Muchas Gracias por tu compra"
                body = f"Visita la sección Mi Cuenta para ver las nuevas claves"
                url = "MyAccount"

                notification = send_push_notification(token, title, body, url)
            except:
                pass

            if customer.email != 'example@example.com':
                Email.email_passwords(request, customer.email, (sale,))

        return True, sale

    def renew_sale(request, old):
        service = request.POST.get('serv')
        price = request.POST.get('price')
        duration = int(request.POST.get('duration'))
        ticket = request.POST.get('comp')
        bank_selected = Bank.objects.get(pk=request.POST.get('bank'))
        payment_used = PaymentMethod.objects.get(pk=request.POST.get('method'))
        customer = User.objects.get(pk=request.POST.get('customer'))
        old_sale = Sale.objects.get(pk=old)
        acc = Account.objects.get(pk=old_sale.account.id)
        if Sale.objects.get(pk=old).expiration_date.date() >= timezone.now().date():
            exp_date = old_sale.expiration_date.date() + relativedelta(months=duration)
        else:
            exp_date = timezone.now() + relativedelta(months=duration)

        # create sale
        new_sale = Sale.objects.create(
            business=request.user.userdetail.business,
            user_seller=request.user,
            bank=bank_selected,
            customer=customer,
            account=acc,
            status=True,
            payment_method=payment_used,
            expiration_date=exp_date,
            payment_amount=price,
            invoice=ticket,
            old_acc=old
        )
        # update account
        acc.modified_by = request.user
        acc.save()

        new_sale_id = new_sale.id

        # deprecate old sale
        old_sale.status = False
        old_sale.old_sale = new_sale_id
        old_sale.save()

        try:
            token = UserDetail.objects.get(user=customer).token
            title = f"Tu cuenta ha sido renovada"
            body = f"Tu nuevo vencimiento es {exp_date}, haz click en aceptar para ver el detalle."
            url = "MyAccount"

            notification = send_push_notification(token, title, body, url)
        except:
            pass

        if customer.email != 'example@example.com':
            Email.email_passwords(request, customer.email, (new_sale,))

        return True

    def change_sale(request):
        sale = request.POST.get('sale')
        service = request.POST.get('serv')
        price = 0
        ticket = 'Cambio'
        try:
            payment_used = PaymentMethod.objects.get(description='Cambio')
        except PaymentMethod.DoesNotExist:
            payment_used = None

        # suspend old Sale
        old_sale = Sale.objects.get(pk=sale)
        old_sale.status = False
        old_sale.save()

        # suspend old acc
        old_acc = Account.objects.get(pk=old_sale.account.id)
        old_acc.customer = None
        old_acc.status = False
        old_acc.save()

        acc = Account.objects.get(pk=service)
        # create sale
        new_sale = Sale.objects.create(
            business=request.user.userdetail.business,
            user_seller=request.user,
            customer=old_sale.customer,
            account=acc,
            status=True,
            payment_method=payment_used,
            expiration_date=old_sale.expiration_date,
            payment_amount=price,
            invoice=ticket
        )
        new_sale_id = new_sale.id
        old_sale.old_acc = new_sale_id
        old_sale.save()
        # update account
        acc.customer = old_sale.customer
        acc.modified_by = request.user
        acc.save()

        try:
            token = UserDetail.objects.get(user=old_sale.customer).token
            title = f"Tu cuenta {acc.account_name.description} ha sido cambiada"
            body = f"Haz click en aceptar para ver el detalle o visita la seccion Mi Cuenta."
            url = "MyAccount"

            notification = send_push_notification(token, title, body, url)
        except:
            pass

        if old_sale.customer.email != 'example@example.com':
            Email.email_passwords(
                request, old_sale.customer.email, (new_sale,))

        return True

    def customer_sales_active(customer):
        active = Sale.objects.filter(
            customer=customer,
            status=True
        )
        return active

    def customer_sales_inactive(customer):
        inactive = Sale.objects.filter(
            customer=customer,
            status=False
        )
        return inactive

    def render_view(request, customer=None, message=None, copy=None):

        if customer == None:
            my_dict = {
                'availables': Sales.availables()[0],
                'message': message,
                'active': Sales.customer_sales_active(customer),
                'inactive': Sales.customer_sales_inactive(customer)
            }
            return render(request, 'adm/sale.html', my_dict)
        else:
            try:
                customer = User.objects.get(pk=customer)
            except TypeError:
                pass
            my_dict = {
                'availables': Sales.availables()[0],
                'customer': customer,
                'message': message,
                'copy': copy,
                'active': Sales.customer_sales_active(customer),
                'inactive': Sales.customer_sales_inactive(customer)
            }
            return render(request, 'adm/sale.html', my_dict)

    def search_better_acc(service_id, exp, code=None):
        # Si no hay codigo o hay pero esta libre
        if code == None or not Cupon.objects.get(name=code).customer:
            try:
                # Busca el objeto con el id del servicio
                service = Service.objects.get(pk=service_id)
            except Service.DoesNotExist:
                # Si no existe arroja error
                return False, "La cuenta seleccionada no existe. Porfavor contactarse al whats app +521 833 535 5863."

            # Declaramos la fecha de vencimiento
            esta = None
            exp1 = f'{exp.date()} 00:00:00'
            exp2 = f'{exp.date()} 23:59:59'
            try:
                # Buscamos todas las ventas que venzan el dia exacto buscado
                account = Sale.objects.filter(account__account_name=service, expiration_date__gte=exp1,
                                              expiration_date__lte=exp2, status=True).order_by('expiration_date')

                if account.count() == 0:
                    # Si no existe elevamos error de que no hay fechas exactas para buscar aproximados
                    raise Sale.DoesNotExist
                else:
                    for a in account:
                        # Busca cuentas libres con relacion a la busqueda anterior
                        selected = Account.objects.filter(
                            account_name=service, email=a.account.email, status=True, customer=None)
                        if selected.count() > 0:
                            # si existe una retorna el resultado
                            return True, selected[0]
                        else:
                            # si no existen cuentas disponibles sigue buscando
                            raise Sale.DoesNotExist
            except Sale.DoesNotExist:

                # find empty accounts
                empty = Account.objects.filter(
                    account_name=service, status=True, customer=None)
                if empty.count() == 0:
                    return False, "No hay cuentas disponibles, porfavor comunicate al whats app +521 833 535 5863"
                for e in empty:
                    q = Account.objects.filter(
                        email=e.email, account_name=service, status=True, customer=None)
                    if q.count() == service.perfil_quantity:
                        return True, q[0]
                if not esta:

                    account = Sale.objects.filter(
                        account__account_name=service, expiration_date__gte=exp1, status=True).order_by('expiration_date')
                    if account.count() > 0:
                        for a in account:
                            acc = Account.objects.filter(
                                email=a.account.email, password=a.account.password, account_name=a.account.account_name, customer=None, status=True)
                            if acc.count() > 0:
                                return True, acc[0]
                            else:
                                acc = Account.objects.filter(
                                    account_name=service, customer=None, status=True, renovable=True)
                                if acc.count() > 0:
                                    return True, acc[0]
                    else:
                        return False, "No hay cuentas disponibles, porfavor comunicate al whats app +521 833 535 5863"
        else:
            return False, "El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo."

    def redeem(request, acc, code, customer_id):
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
                business=Business.objects.get(pk=1),
                bank_name='Shops',
                headline='Cuentas Mexico',
                card_number='0',
                clabe='0',
            )
        try:
            payment_used = PaymentMethod.objects.get(description='Codigo')
        except PaymentMethod.DoesNotExist:
            payment_used = PaymentMethod.objects.create(description='Codigo')

        try:
            sale = Sale.objects.get(invoice=ticket)
        except Sale.DoesNotExist:
            # create sale
            sale = Sale.objects.create(
                business=Business.objects.get(pk=1),
                user_seller=User.objects.get(pk=1),
                bank=bank_selected,
                customer=customer,
                account=service,
                status=True,
                payment_method=payment_used,
                expiration_date=timezone.now() + relativedelta(months=duration),
                payment_amount=price,
                invoice=ticket
            )
            # update account
            service.customer = customer
            service.modified_by = User.objects.get(pk=1)
            service.save()

            # Update Cupon
            cupon.used_at = timezone.now()
            cupon.customer = customer
            cupon.seller = User.objects.get(pk=1)
            cupon.order = sale
            cupon.status_sale = True
            cupon.status = False
            cupon.save()

            try:
                token = UserDetail.objects.get(user=customer).token
                title = f"Muchas Gracias por tu compra"
                body = f"Visita la sección Mi Cuenta para ver las nuevas claves"
                url = "MyAccount"

                notification = send_push_notification(token, title, body, url)
            except:
                pass

            if customer.email != 'example@example.com':
                Email.email_passwords(request, customer.email, (sale,))

        return True

    def redeem_renew(request, acc, code, customer_id):
        cupon = Cupon.objects.get(name=code)
        if cupon.status == True:
            price = cupon.price
            duration = cupon.long
            ticket = code
            try:
                bank_selected = Bank.objects.get(bank_name='Shops')
            except Bank.DoesNotExist:
                bank_selected = Bank.objects.create(
                    business=Business.objects.get(pk=1),
                    bank_name='Shops',
                    headline='Cuentas Mexico',
                    card_number='0',
                    clabe='0',
                )
            try:
                payment_used = PaymentMethod.objects.get(description='Codigo')
            except PaymentMethod.DoesNotExist:
                payment_used = PaymentMethod.objects.create(
                    description='Codigo')
            customer = User.objects.get(pk=customer_id)
            old_sale = Sale.objects.get(account_id=acc, status=True)
            old_acc = Account.objects.get(pk=old_sale.account.id)
            if old_sale.expiration_date.date() >= timezone.now().date():
                exp_date = old_sale.expiration_date.date() + relativedelta(months=duration)
            else:
                exp_date = timezone.now() + relativedelta(months=duration)

            # create sale
            new_sale = Sale.objects.create(
                business=Business.objects.get(pk=1),
                user_seller=User.objects.get(pk=1),
                bank=bank_selected,
                customer=customer,
                account=acc,
                status=True,
                payment_method=payment_used,
                expiration_date=exp_date,
                payment_amount=price,
                invoice=ticket,
                old_acc=old_acc.id
            )
            # update account
            acc.modified_by = User.objects.get(pk=1)
            acc.save()

            new_sale_id = new_sale.id

            # deprecate old sale
            old_sale.status = False
            old_sale.old_sale = new_sale_id
            old_sale.save()

            # Update Cupon
            cupon.used_at = timezone.now()
            cupon.customer = customer
            cupon.seller = User.objects.get(pk=1)
            cupon.order = new_sale
            cupon.status_sale = True
            cupon.status = False
            cupon.save()

            try:
                token = UserDetail.objects.get(user=customer).token
                title = f"Muchas Gracias por tu compra"
                body = f"Visita la sección Mi Cuenta para ver las nuevas claves"
                url = "MyAccount"

                notification = send_push_notification(token, title, body, url)
            except:
                pass

            if customer.email != 'example@example.com':
                Email.email_passwords(request, customer.email, (new_sale,))

            return True, acc
        else:
            return False, "El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo."

    def credits_modify(customer, credits, comments):
        Credits.objects.create(
            customer=customer,
            credits=credits,
            detail=comments
        )

    def web_sale(request, acc, unit_price, months, customer_id=None):
        sale = Sales.cupon_sale(request=request, service=acc, price=unit_price,
                                duration=months, ticket='Web', customer_id=customer_id)
        dict_sale = {
            'id': sale[1].id,
            'logo': sale[1].account.account_name.logo,
            'account_name': sale[1].account.account_name.description,
            'email': sale[1].account.email,
            'password': sale[1].account.password,
            'profile': sale[1].account.profile,
            'pin': sale[1].account.pin,
            'expiration_date': sale[1].expiration_date
        }
        return dict_sale

    def sale_ok(customer, webhook_provider, payment_type, payment_id, service_obj, expiration_date, unit_price):
        try:
            bank_selected = Bank.objects.get(bank_name=webhook_provider)
        except Bank.DoesNotExist:
            bank_selected = Bank.objects.create(
                business=Business.objects.get(pk=1),
                bank_name=webhook_provider,
                headline=webhook_provider,
                card_number='0',
                clabe='0',
            )
        try:
            payment_used = PaymentMethod.objects.get(
                description=payment_type)
        except PaymentMethod.DoesNotExist:
            payment_used = PaymentMethod.objects.create(
                description=payment_type)

        # create sale
        sale = Sale.objects.create(
            business=Business.objects.get(pk=1),
            user_seller=customer,
            bank=bank_selected,
            customer=customer,
            account=service_obj,
            status=True,
            payment_method=payment_used,
            expiration_date=expiration_date,
            payment_amount=unit_price,
            invoice=payment_id
        )
        # update account
        service_obj.customer = customer
        service_obj.modified_by = customer
        service_obj.save()

        return True, sale









