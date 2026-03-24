from adm.functions.send_whatsapp_notification import Notification
from adm.models import (
    Account,
    Service,
    UserDetail,
    Bank,
    PaymentMethod,
    Sale,
    Status,
    Business,
    Credits,
    AccountChangeHistory,
    MarketingCampaign,
    MarketingCampaignDelivery,
    MarketingCampaignRedemption,
)
from api.functions.notifications import send_push_notification
from cupon.models import Cupon, CouponRedemption
from cupon.services import consume_coupon, validate_coupon_from_code
from django.contrib.auth.models import User
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from adm.functions.send_email import Email
from adm.functions.marketing_tags import marketing_tags_for_sales_view
from django.utils import timezone
from datetime import timedelta
from traceback import format_exc
from datetime import datetime
from django.db.models import Count, Q, F
from django.db.models import Min
from math import ceil, floor
import re
import unicodedata


class Sales():
    @staticmethod
    def _normalize_token(value):
        raw = str(value or '').strip().lower()
        if not raw:
            return ''
        normalized = unicodedata.normalize('NFD', raw)
        return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')

    @staticmethod
    def _extract_campaign_promo_code(campaign):
        meta = campaign.audience_filters or {}
        promo_params = meta.get('promo_params') if isinstance(meta.get('promo_params'), dict) else {}
        from_params = str(promo_params.get('promo_code') or '').strip().upper()
        if from_params:
            return from_params
        from_meta = str(meta.get('promo_code') or '').strip().upper()
        if from_meta:
            return from_meta
        text = f"{campaign.message_text or ''} {campaign.sms_text or ''} {meta.get('cta', '')}"
        candidates = re.findall(r"\b[A-Z][A-Z0-9]{4,20}\b", str(text or '').upper())
        for token in candidates:
            if token in {'WHATSAPP', 'MEXICO', 'NETFLIX', 'DISNEY', 'SPOTIFY'}:
                continue
            return token
        return ''

    @staticmethod
    def _campaign_services(campaign):
        meta = campaign.audience_filters or {}
        promo_params = meta.get('promo_params') if isinstance(meta.get('promo_params'), dict) else {}
        explicit_ids = []
        for raw_id in (promo_params.get('services_ids') or meta.get('service_ids') or []):
            try:
                explicit_ids.append(int(raw_id))
            except Exception:
                continue
        explicit_ids = sorted(list(set(explicit_ids)))
        if explicit_ids:
            services = list(Service.objects.filter(id__in=explicit_ids, status=True).order_by('description'))
            if services:
                return services
        strategy = meta.get('audience_strategy') if isinstance(meta.get('audience_strategy'), dict) else {}
        keywords = promo_params.get('service_keywords') if isinstance(promo_params.get('service_keywords'), list) else []
        if not keywords:
            keywords = strategy.get('service_keywords') if isinstance(strategy.get('service_keywords'), list) else []
        if not keywords:
            keywords = []
            for t in campaign.tags or []:
                tk = Sales._normalize_token(t)
                if tk and len(tk) >= 4:
                    keywords.append(tk)
        qs = Service.objects.filter(status=True)
        matched_ids = set()
        for keyword in keywords:
            k = Sales._normalize_token(keyword)
            if not k:
                continue
            for svc in qs:
                if k in Sales._normalize_token(svc.description):
                    matched_ids.add(svc.id)
        if matched_ids:
            return list(Service.objects.filter(id__in=list(matched_ids), status=True).order_by('description'))
        return []

    @staticmethod
    def _campaign_offer_valid_until(campaign):
        meta = campaign.audience_filters or {}
        promo_params = meta.get('promo_params') if isinstance(meta.get('promo_params'), dict) else {}
        raw = promo_params.get('offer_valid_until') or meta.get('offer_valid_until')
        if raw:
            try:
                dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt
            except Exception:
                pass
        base = campaign.sent_at or campaign.created_at or timezone.now()
        return base + timedelta(days=30)

    @staticmethod
    def customer_marketing_offers(customer):
        if not customer:
            return []

        sent_campaign_ids = list(
            MarketingCampaignDelivery.objects.filter(
                recommendation__customer=customer,
                status='sent',
            ).values_list('campaign_id', flat=True).distinct()
        )
        if not sent_campaign_ids:
            return []

        campaigns = MarketingCampaign.objects.filter(id__in=sent_campaign_ids).order_by('-sent_at', '-created_at')
        offers = []
        now = timezone.now()

        for campaign in campaigns:
            valid_until = Sales._campaign_offer_valid_until(campaign)
            if valid_until and valid_until < now:
                continue
            if MarketingCampaignRedemption.objects.filter(campaign=campaign, customer=customer).exists():
                continue

            promo_code = Sales._extract_campaign_promo_code(campaign)
            if promo_code and CouponRedemption.objects.filter(
                customer=customer,
                cupon__name__iexact=promo_code.lower(),
            ).exists():
                continue

            services = Sales._campaign_services(campaign)
            if not services:
                continue

            meta = campaign.audience_filters or {}
            promo_params = meta.get('promo_params') if isinstance(meta.get('promo_params'), dict) else {}
            duration_months = int(promo_params.get('duration_months') or meta.get('duration_months') or 1)
            duration_months = max(1, min(duration_months, 24))

            offer_price = promo_params.get('offer_price')
            if offer_price in (None, ''):
                offer_price = meta.get('offer_price') or meta.get('recommended_price')
            if offer_price is None:
                text_blob = f"{campaign.message_text or ''} {campaign.sms_text or ''}"
                m = re.search(r"\$\s*(\d{2,5})", text_blob)
                if m:
                    offer_price = int(m.group(1))
            if offer_price is None:
                offer_price = int(min(s.price for s in services))
            offer_price = int(max(1, offer_price))

            offers.append(
                {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'promo_code': promo_code,
                    'offer_price': offer_price,
                    'duration_months': duration_months,
                    'valid_until': valid_until,
                    'services': [{'id': s.id, 'name': s.description, 'base_price': s.price} for s in services],
                    'services_ids': [s.id for s in services],
                    'details': promo_params.get('notes') or meta.get('targeting_notes') or meta.get('cta') or '',
                }
            )
        return offers


    def find_best_account(service_id, months_requested):
        """
        Encuentra la mejor cuenta disponible basada en 3 criterios de prioridad:
        1. Menor número de cortes estimados (prioridad máxima)
        2. Mayor tiempo hasta el primer corte (prioridad media)
        3. Menor cantidad de perfiles vacíos (prioridad baja)

        Args:
            service_id: ID del servicio (ej: Netflix)
            months_requested: Duración en meses que el cliente compró

        Returns:
            Account object o None si no hay cuentas disponibles
        """
        from django.db.models import Min

        try:
            service = Service.objects.get(pk=service_id)
        except Service.DoesNotExist:
            return None

        # Obtener todas las cuentas disponibles (sin cliente asignado)
        available_accounts = Account.objects.filter(
            account_name=service,
            status=True,
            customer=None,
            external_status='Disponible'
        ).select_related('account_name')

        if not available_accounts.exists():
            return None

        # Calcular días totales de la suscripción
        dias_totales = months_requested * 30
        now = timezone.now()

        # Lista para almacenar cuentas con sus métricas calculadas
        candidates = []

        # Agrupar cuentas por email+password para calcular perfiles vacíos
        email_groups = {}
        for account in available_accounts:
            key = f"{account.email}|{account.password}"
            if key not in email_groups:
                email_groups[key] = []
            email_groups[key].append(account)

        for account in available_accounts:
            # Buscar la venta activa más próxima a vencer para este email
            next_sale = Sale.objects.filter(
                account__email=account.email,
                account__password=account.password,
                account__account_name=service,
                status=True,
                expiration_date__gte=now
            ).order_by('expiration_date').first()

            # Calcular días hasta el próximo corte
            if next_sale:
                dias_hasta_corte = (next_sale.expiration_date - now).days
            else:
                # Si no hay ventas activas, asumimos que es una cuenta "nueva"
                # Le damos un valor muy alto para que sea preferida
                dias_hasta_corte = 999999

            # Criterio 1: Calcular número de cortes estimados
            if dias_hasta_corte >= dias_totales:
                cortes = 0  # No habrá cortes durante la suscripción
            elif dias_hasta_corte <= 0:
                # Cuenta ya vencida (no debería pasar pero por seguridad)
                cortes = ceil(dias_totales / 30)
            else:
                # Habrá al menos un corte, calcular cuántos más
                cortes = 1 + floor((dias_totales - dias_hasta_corte) / 30)

            # Criterio 3: Contar perfiles vacíos en el mismo email|password
            key = f"{account.email}|{account.password}"
            perfiles_vacios = len(email_groups[key])

            candidates.append({
                'account': account,
                'cortes': cortes,
                'dias_hasta_corte': dias_hasta_corte,
                'perfiles_vacios': perfiles_vacios
            })

        # Ordenar por los 3 criterios en orden de prioridad
        candidates.sort(key=lambda x: (
            x['cortes'],              # 1. Menor cortes (ascendente)
            -x['dias_hasta_corte'],   # 2. Mayor días hasta corte (descendente)
            x['perfiles_vacios']      # 3. Menor perfiles vacíos (ascendente)
        ))

        # Retornar la mejor cuenta
        return candidates[0]['account'] if candidates else None

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
                status=True, customer=None, account_name=a, external_status='Disponible').count()
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
        duration_value = request.POST.get('duration')

        # Debe existir al menos un servicio seleccionado
        if not service:
            return False

        # Validar que duration no sea None o 'None'
        if not duration_value or duration_value == 'None':
            return False

        try:
            duration = int(duration_value)
        except (ValueError, TypeError):
            return False

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
                if acc.pin == None:
                    acc.pin = "No tiene Pin"
                message = f"E-Mail: {acc.email}\n"
                message += f"Clave: {acc.password}\n"
                message += f"Perfil: {acc.profile}\n"
                message += f"Pin: {acc.pin}\n"
                message += f"Vencimiento: {sale.expiration_date.date()}\n\n"
                message += f"💎 Esta es su cuenta {acc.account_name.description} para 1 Dispositivo.\n"
                message += f"Inicie sesión con el EMAIL y CLAVE recibidos.\n\n"
                message += f"* Usar SOLO EL PERFIL ASIGNADO\n"
                message += f"* NO puedes cambiar las claves.\n\n"
                message += f"Gracias por tu preferencia.\n"
                message += f"Recuerda que los únicos canales oficiales de atención son:\n"
                message += f"WhatsApp  al número 833 535 5863 y la web cuentasmexico.com"
                customer_detail = UserDetail.objects.get(user=customer)
                Notification.send_whatsapp_notification(message,customer_detail.lada,customer_detail.phone_number)
                try:
                    token = UserDetail.objects.get(user=customer).token
                    title = f"Muchas Gracias por tu compra"
                    body = f"Para ver las claves de tu cuenta {acc.account_name.description} da click en el botón de abajo o visita la seccion Mi Cuenta"
                    url = "MyAccount"
                    notification = send_push_notification(
                        token, title, body, url)
                except:
                    pass

                # Enviar email si tenemos email del cliente y no es un email de ejemplo
                if customer.email and customer.email != 'example@example.com':
                    try:
                        Email.email_passwords(request, customer.email, (sale,))
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error enviando email a {customer.email}: {str(e)}")
            else:
                continue
        return True

    def cupon_sale(request=None, service=None, price=None, duration=None, ticket=None, customer_id=None, bank_name='Web', payment_used="Saldo Distribuidor"):
        c = request.POST.get('code') if request else None

        if customer_id:
            customer = User.objects.get(pk=customer_id)
        elif request and request.POST.get('customer'):
            customer = User.objects.get(pk=request.POST.get('customer'))
        else:
            customer = User.objects.get(pk=request.user.id)

        cupon = None
        expiration_date = timezone.now() + timedelta(days=30 * int(duration or 1))
        seller = customer

        if c:
            service = Account.objects.get(pk=request.POST.get('serv'))
            cupon = validate_coupon_from_code(c, customer, service=service.account_name)
            price = cupon.price
            ticket = cupon.name
            bank_name = 'Shops'
            payment_used = 'Codigo'
            expiration_date = cupon.get_expiration_date(timezone.now())
            seller = request.user

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
            payment_used = PaymentMethod.objects.create(description=payment_used)

        if c:
            with transaction.atomic():
                sale = Sale.objects.create(
                    business=Business.objects.get(pk=1),
                    user_seller=seller,
                    bank=bank_selected,
                    customer=customer,
                    account=service,
                    status=True,
                    payment_method=payment_used,
                    expiration_date=expiration_date,
                    payment_amount=price,
                    invoice=ticket
                )
                service.customer = customer
                service.modified_by = request.user
                service.save()
                consume_coupon(
                    code_name=cupon.name,
                    customer=customer,
                    seller=request.user,
                    sale=sale,
                    channel=CouponRedemption.CHANNEL_ADMIN,
                    account=service,
                )
        else:
            try:
                sale = Sale.objects.get(invoice=ticket)
                if ticket == 'Web':
                    raise Sale.DoesNotExist
            except Sale.MultipleObjectsReturned:
                if ticket == 'Web':
                    sale = Sale.objects.create(
                        business=Business.objects.get(pk=1),
                        user_seller=customer,
                        bank=bank_selected,
                        customer=customer,
                        account=service,
                        status=True,
                        payment_method=payment_used,
                        expiration_date=expiration_date,
                        payment_amount=price,
                        invoice=ticket
                    )
                    service.customer = customer
                    service.modified_by = customer
                    service.save()
                return True, sale
            except Sale.DoesNotExist:
                sale = Sale.objects.create(
                    business=Business.objects.get(pk=1),
                    user_seller=customer,
                    bank=bank_selected,
                    customer=customer,
                    account=service,
                    status=True,
                    payment_method=payment_used,
                    expiration_date=expiration_date,
                    payment_amount=price,
                    invoice=ticket
                )
                service.customer = customer
                service.modified_by = request.user
                service.save()

        try:
            token = UserDetail.objects.get(user=customer).token
            title = "Muchas Gracias por tu compra"
            body = "Visita la sección Mi Cuenta para ver las nuevas claves"
            url = "MyAccount"
            send_push_notification(token, title, body, url)
        except Exception:
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
            account_name = acc.account_name
            account_email = acc.email
            message = (
                f"Hemos renovado la fecha de vencimiento, de tu cuenta {account_name} "
                f"con email {account_email} ahora vence el {exp_date.strftime('%d/%m/%Y')}"
            )
            customer_detail = UserDetail.objects.get(user=customer.id)
            Notification.send_whatsapp_notification(
                message,
                customer_detail.lada,
                customer_detail.phone_number
            )
        except:
            pass

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

        # Registrar historial trazable del cambio desde /adm
        customer_phone = None
        try:
            customer_phone = old_sale.customer.userdetail.phone_number
        except Exception:
            customer_phone = None

        AccountChangeHistory.objects.create(
            source='admin',
            customer=old_sale.customer,
            changed_by=request.user,
            service=old_acc.account_name,
            old_sale=old_sale,
            new_sale=new_sale,
            old_account=old_acc,
            new_account=acc,
            customer_username=old_sale.customer.username,
            customer_email=old_sale.customer.email,
            customer_phone=customer_phone,
            old_account_email=old_acc.email,
            new_account_email=acc.email,
            old_account_profile=old_acc.profile,
            new_account_profile=acc.profile,
            old_sale_expiration=old_sale.expiration_date,
            new_sale_expiration=new_sale.expiration_date,
            notes='Cambio ejecutado por operador en /adm/sales_change.'
        )

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
        ).select_related('account__account_name', 'account', 'user_seller')
        return active

    def customer_sales_inactive(customer, page=1):
        from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
        
        inactive = Sale.objects.filter(
            customer=customer,
            status=False
        ).select_related('account__account_name', 'account', 'user_seller').order_by('-created_at')
        
        # Paginación para inactivos (15 por página)
        paginator = Paginator(inactive, 15)
        
        try:
            inactive_page = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            inactive_page = paginator.page(1)
            
        return inactive_page

    def render_view(request, customer=None, message=None, copy=None):
        # Obtener parámetro de página para inactivos
        inactive_page = request.GET.get('inactive_page', 1)
        
        if customer == None:
            my_dict = {
                'availables': Sales.availables()[0],
                'message': message,
                'active': Sales.customer_sales_active(customer),
                'inactive': Sales.customer_sales_inactive(customer, inactive_page),
                'marketing_offers': [],
                'marketing_tags': [],
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
                'inactive': Sales.customer_sales_inactive(customer, inactive_page),
                'marketing_offers': Sales.customer_marketing_offers(customer),
                'marketing_tags': marketing_tags_for_sales_view(customer),
            }
            return render(request, 'adm/sale.html', my_dict)

    def search_better_acc(service_id, exp, code=None):
        """
        DEPRECADO: Usa find_best_account() para nueva implementación.
        Esta función mantiene compatibilidad con código legacy pero ahora
        usa la lógica optimizada de find_best_account().

        Args:
            service_id: ID del servicio
            exp: Fecha de expiración deseada (datetime)
            code: Código de cupón (opcional)

        Returns:
            (True, Account) si encuentra cuenta
            (False, mensaje_error) si no encuentra o hay error
        """
        # Calcular cuántos meses se están pidiendo basado en la fecha de expiración
        now = timezone.now()
        dias_diferencia = (exp - now).days
        months_requested = max(1, round(dias_diferencia / 30))

        # Usar la nueva lógica optimizada
        best_account = Sales.find_best_account(
            service_id=service_id,
            months_requested=months_requested
        )

        if best_account:
            return True, best_account
        else:
            return False, "No hay cuentas disponibles, porfavor comunicate al whats app +521 833 535 5863"

    def search_better_acc_legacy(service_id, exp, code=None):
        """
        FUNCIÓN LEGACY ORIGINAL - Mantenida solo como referencia.
        NO USAR - puede retornar None y causar bugs.
        """
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
                            account_name=service, email=a.account.email, status=True, customer=None, external_status='Disponible')
                        if selected.count() > 0:
                            # si existe una retorna el resultado
                            return True, selected[0]
                        else:
                            # si no existen cuentas disponibles sigue buscando
                            raise Sale.DoesNotExist
            except Sale.DoesNotExist:

                # find empty accounts
                empty = Account.objects.filter(
                    account_name=service, status=True, customer=None, external_status='Disponible')
                if empty.count() == 0:
                    return False, "No hay cuentas disponibles, porfavor comunicate al whats app +521 833 535 5863"
                for e in empty:
                    q = Account.objects.filter(
                        email=e.email, account_name=service, status=True, customer=None, external_status='Disponible')
                    if q.count() == service.perfil_quantity:
                        return True, q[0]
                if not esta:

                    account = Sale.objects.filter(
                        account__account_name=service, expiration_date__gte=exp1, status=True).order_by('expiration_date')
                    if account.count() > 0:
                        for a in account:
                            acc = Account.objects.filter(
                                email=a.account.email, password=a.account.password, account_name=a.account.account_name, customer=None, status=True, external_status='Disponible')
                            if acc.count() > 0:
                                return True, acc[0]
                            else:
                                acc = Account.objects.filter(
                                    account_name=service, customer=None, status=True, renovable=True, external_status='Disponible')
                                if acc.count() > 0:
                                    return True, acc[0]
                    else:
                        return False, "No hay cuentas disponibles, porfavor comunicate al whats app +521 833 535 5863"
        else:
            return False, "El código ya fue utilizado, si no lo canjeó usted contacte a su vendedor y pidale uno nuevo."

    def redeem(request, acc, code, customer_id):
        customer = User.objects.get(pk=customer_id)
        cupon = validate_coupon_from_code(code, customer, service=acc.account_name)
        service = acc
        price = cupon.price
        ticket = cupon.name
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

        with transaction.atomic():
            sale = Sale.objects.create(
                business=Business.objects.get(pk=1),
                user_seller=User.objects.get(pk=1),
                bank=bank_selected,
                customer=customer,
                account=service,
                status=True,
                payment_method=payment_used,
                expiration_date=cupon.get_expiration_date(timezone.now()),
                payment_amount=price,
                invoice=ticket
            )
            service.customer = customer
            service.modified_by = User.objects.get(pk=1)
            service.save()
            consume_coupon(
                code_name=cupon.name,
                customer=customer,
                seller=User.objects.get(pk=1),
                sale=sale,
                channel=CouponRedemption.CHANNEL_WEB,
                account=service,
            )

        try:
            token = UserDetail.objects.get(user=customer).token
            title = "Muchas Gracias por tu compra"
            body = "Visita la sección Mi Cuenta para ver las nuevas claves"
            url = "MyAccount"
            send_push_notification(token, title, body, url)
        except Exception:
            pass

        if customer.email != 'example@example.com':
            Email.email_passwords(request, customer.email, (sale,))

        return True

    def redeem_renew(request, acc, code, customer_id):
        customer = User.objects.get(pk=customer_id)
        cupon = validate_coupon_from_code(code, customer, service=acc.account_name)
        price = cupon.price
        ticket = cupon.name
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
        old_sale = Sale.objects.get(account_id=acc, status=True)
        old_acc = Account.objects.get(pk=old_sale.account.id)
        if old_sale.expiration_date.date() >= timezone.now().date():
            exp_date = cupon.get_expiration_date(old_sale.expiration_date)
        else:
            exp_date = cupon.get_expiration_date(timezone.now())

        with transaction.atomic():
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
            acc.modified_by = User.objects.get(pk=1)
            acc.save()

            new_sale_id = new_sale.id
            old_sale.status = False
            old_sale.old_sale = new_sale_id
            old_sale.save()

            consume_coupon(
                code_name=cupon.name,
                customer=customer,
                seller=User.objects.get(pk=1),
                sale=new_sale,
                channel=CouponRedemption.CHANNEL_WEB,
                account=acc,
            )

        try:
            token = UserDetail.objects.get(user=customer).token
            title = "Muchas Gracias por tu compra"
            body = "Visita la sección Mi Cuenta para ver las nuevas claves"
            url = "MyAccount"
            send_push_notification(token, title, body, url)
        except Exception:
            pass

        if customer.email != 'example@example.com':
            Email.email_passwords(request, customer.email, (new_sale,))

        return True, acc

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
            'logo': sale[1].account.account_name.logo.url,
            'account_name': sale[1].account.account_name.description,
            'email': sale[1].account.email,
            'password': sale[1].account.password,
            'profile': sale[1].account.profile,
            'pin': sale[1].account.pin,
            'expiration_date': sale[1].expiration_date
        }
        return dict_sale

    def sale_ok(customer, webhook_provider, payment_type, payment_id, service_obj, expiration_date, unit_price, request=None):
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

        # Enviar email con las claves del servicio si tenemos email del cliente y no es un email de ejemplo
        if customer.email and customer.email != 'example@example.com':
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Intentando enviar email a {customer.email} para venta {sale.id}")
                
                # Obtener la venta para enviar las claves
                sales = Sale.objects.filter(account=service_obj, customer=customer).order_by('-created_at')[:1]
                if sales:
                    result = Email.email_passwords(request, customer.email, sales)
                    if result:
                        logger.info(f"Email enviado exitosamente a {customer.email}")
                    else:
                        logger.warning(f"No se pudo enviar email a {customer.email}")
            except Exception as e:
                # Log el error pero no falles la venta
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error enviando email a {customer.email}: {str(e)}", exc_info=True)

        return True, sale
