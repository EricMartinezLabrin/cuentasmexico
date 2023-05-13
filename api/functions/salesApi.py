from adm.functions.send_email import Email
from adm.models import Account, Business, PaymentMethod, Sale, Service, UserDetail
from django.contrib.auth.models import User
from adm.functions.sales import Sales
from api.functions.notifications import send_push_notification


class SalesApi():
    def SalesCreateApi(request, payer, service_id, expiration_date, payment_method, payment_amount, order_id):
        business = Business.objects.get(pk=1)
        try:
            payer = User.objects.get(username=payer)
        except User.DoesNotExist:
            payer = User.objects.create_user(
                username=payer, password="api", email=payer)
        except User.MultipleObjectsReturned:
            payer = User.objects.filter(email=payer).first()
        try:
            seller = User.objects.get(username="api")
        except User.DoesNotExist:
            seller = User.objects.create_user(
                username="api", password="api", email="example@example.com")

        try:
            payment_method = PaymentMethod.objects.get(
                description=payment_method)
        except PaymentMethod.DoesNotExist:
            payment_method = PaymentMethod.objects.create(
                description=payment_method)

        best_account = Sales.search_better_acc(
            service_id=service_id, exp=expiration_date)
        if best_account[0] == True:
            account = best_account[1]

            # Create Sale
            sale = Sale.objects.create(
                business=business,
                user_seller=seller,
                customer=payer,
                account=account,
                payment_method=payment_method,
                expiration_date=expiration_date,
                payment_amount=int(payment_amount),
                invoice=order_id
            )
            # Update Account
            account.customer = payer
            account.modified_by = seller
            account.save()

            # send Notification
            try:
                token = UserDetail.objects.get(user=payer).token
                title = f"Muchas Gracias por tu compra"
                body = f"Para ver las claves de tu cuenta {account.account_name.description} da click en aceptar o visita la seccion Mi Cuenta"
                url = "MyAccount"
                notification = send_push_notification(
                    token, title, body, url)
            except Exception as e:
                print(e)

            if not account.email == 'example@example.com':
                Email.email_passwords(request, account.email, (sale,))
            return sale
        else:
            try:
                account_obj = Service.objects.get(pk=service_id)
            except Service.DoesNotExist:
                return False
            except Service.MultipleObjectsReturned:
                return False
            acc = Account.objects.filter(
                status=True, customer=None, account_name=account_obj)
            if acc.count() > 0:
                account = acc[0]

                # Create Sale
                sale = Sale.objects.create(
                    business=business,
                    user_seller=seller,
                    customer=payer,
                    account=account,
                    payment_method=payment_method,
                    expiration_date=expiration_date,
                    payment_amount=int(payment_amount),
                    invoice=order_id
                )
                # Update Account
                account.customer = payer
                account.modified_by = seller
                account.save()

                # send Notification
                try:
                    token = UserDetail.objects.get(user=payer).token
                    title = f"Muchas Gracias por tu compra"
                    body = f"Para ver las claves de tu cuenta {account.account_name.name} da click en el botón de abajo o visita la seccion Mi Cuenta"
                    url = "MyAccount"
                    notification = send_push_notification(
                        token, title, body, url)
                except:
                    pass

                if not account.email == 'example@example.com':
                    Email.email_passwords(request, account.email, (sale,))
                return sale

            return sale
