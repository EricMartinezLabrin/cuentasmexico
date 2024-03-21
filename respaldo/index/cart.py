from adm.models import Service
from .models import IndexCart, IndexCartdetail


class CartProcessor:
    def __init__(self, request):
        self.request = request
        self.session = request.session
        carrito = self.session.get('cart_number')
        carrito_total = self.session.get('cart_total')
        carrito_cantidad = self.session.get('cart_quantity')
        if not carrito:
            self.session['cart_number'] = {}
            self.carrito = self.session['cart_number']
            self.session['cart_total'] = 0
            self.carrito_total = self.session['cart_total']
            self.session['cart_quantity'] = 0
            self.carrito_cantidad = self.session['cart_quantity']
        else:
            self.carrito = carrito
            self.carrito_total = carrito_total
            self.carrito_cantidad = carrito_cantidad

    def add(self, product, quantity, profiles, price):
        id = str(product.id)
        if id not in self.carrito.keys():
            self.carrito[id] = {
                'product_id': int(product.id),
                'name': product.description,
                'quantity': quantity,
                'profiles': profiles,
                'price': int(price)*quantity*profiles,
                'image': product.logo.url,
                'description': product.description,
                'unitPrice': int(price)
            }
            self.carrito_total = int(
                self.carrito_total) + int(price)*quantity*profiles
            self.carrito_cantidad = int(self.carrito_cantidad)+1
        else:
            for key, value in self.carrito.items():
                if key == str(product.id):
                    self.carrito_total = self.carrito_total-value['price']
                    value['quantity'] = value['quantity']+1
                    value['price'] = price*value['quantity']*value['profiles']
                    self.carrito_total = int(
                        self.carrito_total) + int(value['price'])
                    self.carrito_cantidad = int(self.carrito_cantidad)+1
                    self.save()
                    break
        self.save()

    def save(self):
        self.session['cart_number'] = self.carrito
        self.session['cart_total'] = self.carrito_total
        self.session['cart_quantity'] = self.carrito_cantidad
        self.session.modified = True

    def remove(self, product):
        product_id = str(product.id)
        for key, value in self.carrito.items():
            if key == str(product.id):
                subtotal = value['price']
                quantity = value['quantity']
                break
        if product_id in self.carrito:
            self.carrito_total = self.carrito_total-subtotal
            self.carrito_cantidad = self.carrito_cantidad-quantity
            del self.carrito[product_id]
            self.save()

    def decrement(self, product, unitPrice):
        for key, value in self.carrito.items():
            if key == str(product.id):
                self.carrito_total = self.carrito_total-value['price']
                value['quantity'] = value['quantity']-1
                value['price'] = int(
                    unitPrice*value['quantity']*value['profiles'])
                self.carrito_total = self.carrito_total + value['price']
                self.carrito_cantidad = self.carrito_cantidad - 1
                if value['quantity'] < 1:
                    self.remove(product)
                else:
                    self.save()
                break
            else:
                print("El producto no existe en el carrito")

    def clear(self):
        self.session['cart_number'] = {}
        self.session['cart_total'] = 0
        self.session['cart_quantity'] = 0
        self.session.modified = True


class CartDb:
    def create_cart(
        payment_id=None,
        date_created=None,
        date_approved=None,
        date_last_updated=None,
        money_release_date=None,
        payment_type_id=None,
        status_detail=None,
        currency_id=None,
        description=None,
        transaction_amount=None,
        transaction_amount_refunded=None,
        coupon_amount=None,
        customer=None,
    ):
        cart = IndexCart.objects.create(
            payment_id=payment_id,
            date_created=date_created,
            date_approved=date_approved,
            date_last_updated=date_last_updated,
            money_release_date=money_release_date,
            payment_type_id=payment_type_id,
            status_detail=status_detail,
            currency_id=currency_id,
            description=description,
            transaction_amount=transaction_amount,
            transaction_amount_refunded=transaction_amount_refunded,
            coupon_amount=coupon_amount,
            customer=customer,
        )
        return cart

    def create_cart_details(
        duration,
        quantity,
        price,
        cart,
        service,
    ):
        cart_detail = IndexCartdetail.objects.create(
            long=duration,
            quantity=quantity,
            price=price,
            cart=cart,
            service=service,
        )

        return cart_detail

    def create_full_cart(self):
        cart_data = self.request.session.get('cart_number')
        if cart_data:
            cart = CartDb.create_cart(customer=self.request.user)
            print(cart.id)
            for item in cart_data.items():
                service = Service.objects.get(description=item[1]['name'])
                CartDb.create_cart_details(
                    item[1]['quantity'],
                    item[1]['profiles'],
                    item[1]['unitPrice'],
                    cart,
                    service
                )
            return cart
        return None
