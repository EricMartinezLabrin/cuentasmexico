import csv
import pandas as pd
from adm.models import Service, UserDetail, Account, Supplier, Business, Sale, Bank, PaymentMethod
from cupon.models import Shop, Cupon
from adm.functions.active_inactive import Active_Inactive
from django.contrib.auth.models import User
from adm.functions.country import Country
from datetime import datetime
from django.db import IntegrityError

class ImportData():

    def dateFormat(date):
        if date == '0000-00-00':
            return datetime.now()
        elif date == 'NULL':
            return datetime.now()
        elif date == '0000-00-00 00:00:00':
            return datetime.now()
        elif date == '0000-00-00 00:00:00.000000':
            return datetime.now()
        else:
            return date

    def services():
        print('Comenzamos importacion de Servicios')
        serv_csv = csv.reader(open('media/modificar/cuentas.csv'))
        contador = int(len(pd.read_csv('media/modificar/cuentas.csv')))
        

        for s in serv_csv:
            print(f'Quedan {contador} servicios por importar')
            try:
                Service.objects.get(description=str(s[2]))
                print(f'{s[2]} ya existe')
            except Service.DoesNotExist:
                Service.objects.create(
                    old_id= s[0],
                    description = str(s[2]),
                    perfil_quantity = 0,
                    status = Active_Inactive.a_or_i(str(s[3]))
                )
            contador -= 1
        print('Terminamos importación de servicios')

    def customers():
        print('Comenzamos importacion de Clientes')
        customer_csv = csv.reader(open('media/modificar/clientes.csv'))
        contador = int(len(pd.read_csv('media/modificar/clientes.csv')))

        for c in customer_csv:
            print(f'quedan {contador} clientes por importar')
            business = Business.objects.get(pk=1)

            #eliminamos lada del telefono
            num = ""
            email = None
            for l in str(c[4]):
                if l.isnumeric():
                    num = num+l

            if num == '':
                email = str(c[3])

            elif str(num)[:3] =='521':
                phone = str(num[3:])

            elif str(num[:3]=='569'): 
                phone = str(num[3:])

            elif len(str(num)) == 0:
                email = c[3]

            elif '@' in str(c[4]):
                email = str(c[4])

            elif '@' in str(c[3]):
                email = str(c[3])

            else:
                phone = num

            print(email)

            if phone == '':
                continue
            if len(str(phone))>16:
                continue
            else:
                phone = int(phone)

            #obtenemos lada y nombre del pais
            if c[5] in Country.get_country_lada():
                lada = Country.get_country_lada()[c[5]]
            else:
                lada=0


            #creamos usuario
            if phone:
                try:
                    user = User.objects.get(username=phone)
                    user.email = c[3]
                    user.save()
                    print(f'cliente {user.username} ya existe')
                except User.DoesNotExist:
                    user = User.objects.create_user(phone, str(c[3]), 'cuentasmexico')
                    user.first_name = c[1]
                    user.last_name = c[2]
                    user.save()
                    userdetail = UserDetail.objects.create(
                        business = business,
                        user = user,
                        phone_number = phone,
                        lada =lada,
                        country = c[5],
                        free_days = 0
                    )
            elif email:
                try:
                    user = User.objects.get(email=email)
                    print(f'cliente {user.username} ya existe')
                except User.DoesNotExist:
                    user = User.objects.create_user(email, email, 'cuentasmexico')
                    user.first_name = c[1]
                    user.last_name = c[2]
                    user.save()
                    userdetail = UserDetail.objects.create(
                        business = business,
                        user = user,
                        phone_number = 0,
                        lada =lada,
                        country = c[5],
                        free_days = 0
                    )
            contador -= 1
        print('Terminamos Clientes')

    def accounts(request):
        print('Comenzamos importacion de Acuentas')
        accounts_csv = csv.reader(open('media/modificar/adm_cta.csv'))
        serv_csv = csv.reader(open('media/modificar/cuentas.csv'))
        contador = int(len(pd.read_csv('media/modificar/adm_cta.csv')))
        business = Business.objects.get(pk=1)
        customer_number = None
        customer_email = None

        try:
            supplier = Supplier.objects.get(name='Otro')
        except Supplier.DoesNotExist:
            supplier = Supplier.objects.create(
                    business = business,
                    name = 'Otro',
                    phone_number = 0
            )

        for a in accounts_csv:
            print(f'Quedan {contador} cuentas')
            #sent
            if a[12]=='NULL':
                sent = False
            elif int(a[12]) ==1:
                sent = True
            else:
                sent = False

            try:
                ss = a[10]
                if ss == 'NULL':
                    contador -=1
                    continue

                if a[7] == 'NULL':
                    contador -= 1
                    continue
                else:
                    profile = a[7]

                service = Service.objects.get(old_id=ss)
                acc = Account.objects.get(account_name=service,email=a[5],password=a[6],profile=profile)
                print(f'EL servicio {acc.email} ya existe')
                contador -=1
                continue
                
            except Service.DoesNotExist:
                print(f'Servicio {ss} no existe')
                contador -=1
                continue
                
            except Account.DoesNotExist:
                if a[2] == '0000-00-00':
                    expiration = datetime.now()
                else:
                    expiration = a[2]

                acc = Account.objects.create(
                    business = business,
                    supplier= supplier,
                    status = Active_Inactive.a_or_i(a[13]),
                    created_by = request.user,
                    modified_by = request.user,
                    account_name = Service.objects.get(old_id=a[10]),
                    created_at = datetime.now(),
                    expiration_date = expiration,
                    email = a[5],
                    password = a[6],
                    pin = None,
                    comments = a[3] + ' - ' + a[4],
                    profile = profile,
                    sent = sent,
                    renovable = False
                )
            contador -= 1
            print(f'Servicio {acc.email} creado correctamente')
        print('Terminamos importacion de Cuentas')

    def sales(request):
        print('Comenzamos importacion de Ventas')
        ventas_csv = csv.reader(open('media/modificar/ventas.csv'))
        contador = int(len(pd.read_csv('media/modificar/ventas.csv'))) 

        #bank
        try:
            bank = Bank.objects.get(bank_name='Otro')
        except Bank.DoesNotExist:
            bank = Bank.objects.create(
                business = Business.objects.get(pk=1),
                bank_name = 'Otro',
                headline = 'Cuentas México',
                card_number = 0,
                clabe = 0
            )
        #PaymentMethod
        try:
            payment_method = PaymentMethod.objects.get(description='Otro')
        except PaymentMethod.DoesNotExist:
            payment_method = PaymentMethod.objects.create(description='Otro')

        for v in  ventas_csv:
            print(f'Quedan {contador} ventas por ingresar')
            #customer
            customer_complete = str(v[1])
            if '@' in customer_complete:
                new_customer = customer_complete
            elif customer_complete[:3] == '521':
                new_customer = customer_complete[3:]
            elif customer_complete[:3] == '569':
                new_customer = customer_complete[3:]
            elif customer_complete == '':
                print(f'cliente {customer_complete} no existe ')
                contador -=1
                continue
            else:
                new_customer = customer_complete
            if len(User.objects.filter(username__contains=new_customer)) == 0:
                if '@' in new_customer:
                    try:
                        new_customer=User.objects.get(email__contains=new_customer)
                    except User.DoesNotExist:
                        try:
                            user = User.objects.create_user(new_customer, new_customer, 'cuentasmexico')
                            userdetail = UserDetail.objects.create(
                                business = Business.objects.get(pk=1),
                                user = user,
                                phone_number = 0,
                                lada =0,
                                country = '??',
                                free_days = 0
                            )
                            new_customer=user#User.objects.get(email__contains=new_customer)
                        except IntegrityError:
                            new_customer=User.objects.filter(email__contains=str(new_customer)[1:])
                            if len(new_customer) <= 0:
                                contador -= 1
                                continue
                            else:
                                new_customer = new_customer[0]
                else:
                    try:
                        new_customer=UserDetail.objects.get(phone_number__contains=new_customer)
                    except UserDetail.DoesNotExist:
                        try:    
                            new_customer.isnumber()
                            user = User.objects.create_user(new_customer, 'example@example.com', 'cuentasmexico')
                            userdetail = UserDetail.objects.create(
                                business = Business.objects.get(pk=1),
                                user = user,
                                phone_number = new_customer,
                                lada =0,
                                country = '??',
                                free_days = 0
                            )
                            new_customer=User.objects.get(phone_number__contains=new_customer)
                        except AttributeError:
                            contador -= 1
                            continue
            else:
                new_customer = User.objects.filter(username__contains=new_customer)[0]
            
            #Account Name
            try:
                account_name = Service.objects.get(old_id=v[2])
            except:
                print(f'Cuenta {v[2]} no existe')
                contador -=1
                continue

            if len(str(v[6])) >2 or len(str(v[6])) <= 0:
                print(f'El perfil {v[6]} no existe')
                contador -=1
                continue

            try:
                account = Account.objects.get(email=v[5],profile=v[6],password=v[7],account_name=account_name.id)
            except Account.DoesNotExist:
                account = Account.objects.filter(email=v[5],profile=v[6],account_name=account_name.id)
                if len(account) == 0:
                    print(f'La cuenta no existe')
                    contador -=1
                    continue
                else:
                    account = account[0]

            #Create Sale
            
            try:
                sale = Sale.objects.get(
                    business = Business.objects.get(pk=1),
                    user_seller = request.user,
                    bank = bank,
                    customer = new_customer,
                    account = account,
                    status = Active_Inactive.a_0_or_1(v[8]),
                    payment_method = payment_method,
                    created_at = ImportData.dateFormat(v[3]),
                    expiration_date = ImportData.dateFormat(v[4]),
                    payment_amount = v[10],
                    invoice = v[11],
                    comment = v[9]
            )
                print(f'La cuenta {sale.account.email} ya existe')
                contador -=1
                continue

            except Sale.DoesNotExist:
                sale = Sale.objects.create(
                        business = Business.objects.get(pk=1),
                        user_seller = request.user,
                        bank = bank,
                        customer = new_customer,
                        account = account,
                        status = Active_Inactive.a_0_or_1(v[8]),
                        payment_method = payment_method,
                        created_at = ImportData.dateFormat(v[3]),
                        expiration_date = ImportData.dateFormat(v[4]),
                        payment_amount = v[10],
                        invoice = v[11],
                        comment = v[9]
                )
                #update acc
                if sale.status == True:
                    account.customer = new_customer
                    account.modified_by = request.user
                    account.save()
                print(f'Creando venta a la cuenta {sale.account.email}')

            contador -=1
        print('Ventas Terminadas')

    def bank():
        print('Comenzamos importacion de Cuentas Bancarias')
        bank_csv = csv.reader(open('media/modificar/tarjetas.csv'))
        contador = int(len(pd.read_csv('media/modificar/tarjetas.csv')))

        for b in bank_csv:
            print(f'Quedan {contador} cuentas por terminar')
            try:
                Bank.objects.get(card_number=b[3])
                print(f'Cuenta {b[3]} ya existe')
                contador -= 1
                continue
            except Bank.DoesNotExist:
                Bank.objects.create(
                    business = Business.objects.get(pk=1),
                    bank_name = b[1],
                    headline = b[2],
                    card_number = b[3],
                    clabe = b[4]
                )
                print(f'Cuenta {b[3]} creada')
                contador -= 1
            print('Proceso Terminado')

    def invoices():
        print('Comenzamos importacion de Pagos')
        invo_csv = csv.reader(open('media/modificar/movimientos.csv'))
        contador = int(len(pd.read_csv('media/modificar/movimientos.csv')))

        try:
            transfer = PaymentMethod.objects.get(description = 'Transferencia')
        except PaymentMethod.DoesNotExist:
            transfer = PaymentMethod.objects.create(description = 'Transferencia')
        
        try:
            depo = PaymentMethod.objects.get(description = 'Deposito')
        except PaymentMethod.DoesNotExist:
            depo = PaymentMethod.objects.create(description = 'Deposito')

        for v in invo_csv:
            print(f'Quedan {contador} pagos por importar')

            if int(v[2]) > 0:
                method = transfer
                amo = int(v[2])
            else:
                method = depo
                amo = int(v[3])

            
            if v[5]== '' or v[5] == 'falto':
                print(f'Venta {v[0]} no existe ')
                print('1')
                contador -=1
                continue

            if v[2]== '0' and v[3] == '0':
                print(f'Venta {v[0]} no existe ')
                contador -=1
                continue

            try:
                payment = Sale.objects.get(invoice=v[5])
                payment.payment_method = method
                payment.bank = Bank.objects.get(pk = int(v[1])+1)
                payment.payment_amount = int(amo)
                payment.save()
                contador -= 1
                print(f'${amo} registrados')
                continue
            except Sale.DoesNotExist:
                print(f'Factura {v[5]} no existe')
                contador -=1
                continue
            except Sale.MultipleObjectsReturned:
                print(f'Factura {v[5]} Esta repetida ')
                contador -=1
                continue

        print("Termino proceso")

    def update_country():
        print('Comenzamos importacion de Clientes')
        customer_csv = csv.reader(open('media/modificar/clientes.csv'))
        contador = int(len(pd.read_csv('media/modificar/clientes.csv')))

        for c in customer_csv:
            print(contador)
            customer_full = str(c[4])
            lada = str(c[3])[:3]
            customer_phone = customer_full[3:]
            try:
                customer_id = UserDetail.objects.get(phone_number=str(c[4])[3:]).user.id
            except UserDetail.DoesNotExist:
                continue
            customer = User.objects.get(pk=customer_id)
            if lada == '521':
                customer.country = 'Mexico'
                customer.lada = '521'
                customer.save()
            elif lada == '569':
                customer.country = 'Chile'
                customer.lada = '569'
                customer.save()
            
            contador -=1

    def shop():
        print('Comenzamos importacion de Tiendas')
        shop_csv = csv.reader(open('media/modificar/tiendas.csv'))
        contador = int(len(pd.read_csv('media/modificar/tiendas.csv')))
        
        for s in shop_csv:
            print(f'Quedan {contador} tiendas por crear')
            try:
                Shop.objects.get(name=s[2])
                print(f'Tienda {s[2]} ya existe')
                contador -=1
                continue
            except Shop.DoesNotExist:
                Shop.objects.create(
                    name = s[2],
                    owner = s[1],
                    phone = s[3],
                    email = s[4],
                    giro = s[5],
                    address = s[11],
                    city = s[12],
                    cp = 0,
                    seller = User.objects.get(pk=1),
                    confirmation_date = ImportData.dateFormat(s[13]),
                    comision_date = ImportData.dateFormat(s[14]),
                    confirmation=True,
                    comision=True
                )
                print(f'Tienda {s[2]} creada')
                contador -=1

    def cupon():
        print('Comenzamos importacion de Cupones')
        cupon_csv = csv.reader(open('media/modificar/cupon.csv'))
        contador = int(len(pd.read_csv('media/modificar/cupon.csv')))       
        
        for c in cupon_csv:
            print(f'Quedan {contador} cupones por crear')
            cupon = c[1].lower()
            shop_name = c[11]
            folder_name = c[7]

            if len(cupon) > 30:
                contador -= 1
                continue

            if folder_name == '':
                folder = 0
            elif folder_name == None:
                folder = 0
            else:
                folder = int(folder_name)


            if shop_name == '0':
                shop = None
            elif shop_name == 'NULL':
                shop = None
            elif shop_name == None:
                shop = None
            else:
                shop = Shop.objects.get(name=c[11])

            if c[13] == 'NULL':
                customer = None
            elif c[13] == None:
                customer = None
            else:
                try:
                    customer = User.objects.get(email=c[13])
                except User.DoesNotExist:
                    try:
                        customer = User.objects.get(username=c[13])
                    except User.DoesNotExist:
                        if c[14] == 'NULL':
                            contador -=1
                            continue
                        else:
                            try:
                                customer = UserDetail.objects.get(phone_number=c[14]).user
                            except UserDetail.DoesNotExist:
                                try:
                                    customer = User.objects.get(username=c[14])
                                except User.DoesNotExist:
                                    contador -=1
                                    continue

            try:
                Cupon.objects.get(name=cupon)
                print(f'Cupon {cupon.upper()} ya existe')
                contador -= 1
            except Cupon.DoesNotExist:
                Cupon.objects.create(
                    name = cupon,
                    status = Active_Inactive.activo_or_inactivo(c[2]),
                    long = int(c[5]),
                    price = int(c[6]),
                    folder = folder,
                    create_date = ImportData.dateFormat(c[8]),
                    used_at = ImportData.dateFormat(c[9]), 
                    shop = shop,
                    customer=customer,
                )



